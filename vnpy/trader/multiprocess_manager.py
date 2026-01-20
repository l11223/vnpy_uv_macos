"""
多进程策略执行管理模块

实现多进程策略执行架构，绕过Python GIL限制，充分利用多核CPU。
参考Elite版多进程架构设计，保持与现有单进程策略执行逻辑的向后兼容。
"""

import multiprocessing
import os
import signal
import time
from multiprocessing import Process, Queue, Manager
from queue import Empty
from typing import Any, Callable, Dict, Optional, List
from threading import Thread
import traceback

from .logger import logger
from .platform_utils import is_mac_system


def _signal_handler(signum, frame):
    """信号处理器（Mac系统兼容）- 独立函数，可在子进程中使用"""
    logger.info(f"策略进程收到信号 {signum}")


class ProcessManager:
    """
    多进程策略执行管理器
    
    负责创建、管理和监控策略执行进程，实现进程间通信。
    """
    
    def __init__(self, max_workers: Optional[int] = None):
        """
        初始化进程管理器
        
        Args:
            max_workers: 最大工作进程数，None表示使用CPU核心数
        """
        # Mac系统特定设置：设置进程启动方法
        if is_mac_system():
            try:
                # 尝试设置spawn方法（Mac系统推荐）
                multiprocessing.set_start_method('spawn', force=False)
                logger.info("Mac系统：已设置multiprocessing启动方法为'spawn'")
            except RuntimeError:
                # 如果已经设置过，获取当前方法
                current_method = multiprocessing.get_start_method()
                logger.info(f"Mac系统：multiprocessing启动方法已设置为'{current_method}'")
        
        # 确定最大工作进程数
        if max_workers is None:
            max_workers = multiprocessing.cpu_count()
        self.max_workers = max_workers
        
        # 进程管理
        self.processes: Dict[str, Process] = {}
        self.process_queues: Dict[str, Queue] = {}
        self.process_status: Dict[str, Dict[str, Any]] = {}
        
        # 共享状态管理
        self.manager = Manager()
        self.shared_state = self.manager.dict()
        self.shared_locks = self.manager.dict()  # 共享锁字典
        self.shared_events = self.manager.dict()  # 共享事件字典
        
        # 进程间通信队列（双向）
        self.main_to_process_queues: Dict[str, Queue] = {}  # 主进程到策略进程
        self.process_to_main_queues: Dict[str, Queue] = {}  # 策略进程到主进程
        
        # 监控线程
        self.monitor_thread: Optional[Thread] = None
        self.monitoring = False
        
        logger.info(f"多进程管理器初始化完成，最大工作进程数: {self.max_workers}")
    
    def start_strategy_process(
        self,
        strategy_id: str,
        strategy_func: Callable,
        strategy_args: tuple = (),
        strategy_kwargs: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        启动策略执行进程
        
        Args:
            strategy_id: 策略唯一标识
            strategy_func: 策略执行函数
            strategy_args: 策略函数位置参数
            strategy_kwargs: 策略函数关键字参数
            
        Returns:
            bool: 是否成功启动
        """
        if strategy_kwargs is None:
            strategy_kwargs = {}
        
        # 检查是否已有该策略进程
        if strategy_id in self.processes:
            logger.warning(f"策略进程 {strategy_id} 已存在")
            return False
        
        # 检查进程数限制
        if len(self.processes) >= self.max_workers:
            logger.warning(f"已达到最大进程数限制 {self.max_workers}，无法启动新策略进程")
            return False
        
        try:
            # 创建双向进程间通信队列
            main_to_process_queue = Queue()
            process_to_main_queue = Queue()
            self.main_to_process_queues[strategy_id] = main_to_process_queue
            self.process_to_main_queues[strategy_id] = process_to_main_queue
            # 保持向后兼容
            self.process_queues[strategy_id] = process_to_main_queue
            
            # 创建共享锁和事件（用于同步）
            shared_lock = self.manager.Lock()
            shared_event = self.manager.Event()
            self.shared_locks[strategy_id] = shared_lock
            self.shared_events[strategy_id] = shared_event
            
            # 创建策略进程
            process = Process(
                target=self._strategy_process_worker,
                args=(
                    strategy_id, 
                    strategy_func, 
                    strategy_args, 
                    strategy_kwargs, 
                    main_to_process_queue,
                    process_to_main_queue,
                    self.shared_state,
                    shared_lock,
                    shared_event
                ),
                name=f"Strategy-{strategy_id}"
            )
            
            # Mac系统特定设置
            # 注意：multiprocessing的启动方法必须在主进程中、在任何Process创建之前设置
            # 这里只做检查，实际设置应该在ProcessManager初始化时完成
            if is_mac_system():
                try:
                    current_method = multiprocessing.get_start_method()
                    if current_method != 'spawn':
                        logger.warning(
                            f"Mac系统建议使用'spawn'启动方法，当前为'{current_method}'。"
                            f"请在创建ProcessManager之前调用multiprocessing.set_start_method('spawn')"
                        )
                except RuntimeError:
                    # 如果已经设置过，忽略错误
                    pass
            
            # 启动进程
            process.start()
            self.processes[strategy_id] = process
            
            # 初始化进程状态
            self.process_status[strategy_id] = {
                'pid': process.pid,
                'start_time': time.time(),
                'status': 'running',
                'restart_count': 0
            }
            
            logger.info(f"策略进程 {strategy_id} 启动成功，PID: {process.pid}")
            
            # 启动监控线程（如果尚未启动）
            if not self.monitoring:
                self.start_monitoring()
            
            return True
            
        except Exception as e:
            logger.error(f"启动策略进程 {strategy_id} 失败: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def _strategy_process_worker(
        self,
        strategy_id: str,
        strategy_func: Callable,
        strategy_args: tuple,
        strategy_kwargs: Dict[str, Any],
        main_to_process_queue: Queue,
        process_to_main_queue: Queue,
        shared_state: Dict[str, Any],
        shared_lock,
        shared_event
    ) -> None:
        """
        策略进程工作函数
        
        在独立进程中执行策略逻辑，通过队列与主进程通信。
        
        Args:
            strategy_id: 策略唯一标识
            strategy_func: 策略执行函数
            strategy_args: 策略函数位置参数
            strategy_kwargs: 策略函数关键字参数
            process_queue: 进程间通信队列
        """
        try:
            # 设置进程信号处理（Mac系统兼容）
            if is_mac_system():
                signal.signal(signal.SIGTERM, _signal_handler)
                signal.signal(signal.SIGINT, _signal_handler)
            
            # 初始化共享状态
            with shared_lock:
                shared_state[f'{strategy_id}_pid'] = os.getpid()
                shared_state[f'{strategy_id}_status'] = 'running'
            
            # 向主进程发送启动消息
            process_to_main_queue.put({
                'type': 'started',
                'strategy_id': strategy_id,
                'pid': os.getpid()
            })
            
            # 设置共享状态中的策略函数参数（如果需要）
            if strategy_kwargs:
                with shared_lock:
                    shared_state[f'{strategy_id}_kwargs'] = strategy_kwargs
            
            # 执行策略函数（传入通信队列和共享状态）
            logger.info(f"策略进程 {strategy_id} 开始执行，PID: {os.getpid()}")
            
            # 将通信接口传递给策略函数（如果策略函数支持）
            enhanced_kwargs = dict(strategy_kwargs)
            enhanced_kwargs['_process_comm'] = {
                'receive_queue': main_to_process_queue,
                'send_queue': process_to_main_queue,
                'shared_state': shared_state,
                'lock': shared_lock,
                'event': shared_event
            }
            
            try:
                strategy_func(*strategy_args, **enhanced_kwargs)
            except TypeError as e:
                # 如果策略函数不接受这些参数，使用原始参数
                if '_process_comm' in str(e) or 'unexpected keyword argument' in str(e):
                    logger.debug(f"策略函数不支持_process_comm参数，使用原始参数: {e}")
                    strategy_func(*strategy_args, **strategy_kwargs)
                else:
                    # 其他TypeError，重新抛出
                    raise
            
            # 向主进程发送完成消息
            process_to_main_queue.put({
                'type': 'completed',
                'strategy_id': strategy_id
            })
            
            # 更新共享状态
            with shared_lock:
                shared_state[f'{strategy_id}_status'] = 'completed'
            
        except KeyboardInterrupt:
            logger.info(f"策略进程 {strategy_id} 收到中断信号")
            with shared_lock:
                shared_state[f'{strategy_id}_status'] = 'interrupted'
            process_to_main_queue.put({
                'type': 'interrupted',
                'strategy_id': strategy_id
            })
        except Exception as e:
            logger.error(f"策略进程 {strategy_id} 执行异常: {e}")
            logger.error(traceback.format_exc())
            with shared_lock:
                shared_state[f'{strategy_id}_status'] = 'error'
                shared_state[f'{strategy_id}_error'] = str(e)
            process_to_main_queue.put({
                'type': 'error',
                'strategy_id': strategy_id,
                'error': str(e),
                'traceback': traceback.format_exc()
            })
        finally:
            logger.info(f"策略进程 {strategy_id} 退出")
    
    def stop_strategy_process(self, strategy_id: str, timeout: float = 5.0) -> bool:
        """
        停止策略执行进程
        
        Args:
            strategy_id: 策略唯一标识
            timeout: 等待进程退出的超时时间（秒）
            
        Returns:
            bool: 是否成功停止
        """
        if strategy_id not in self.processes:
            logger.warning(f"策略进程 {strategy_id} 不存在")
            return False
        
        try:
            process = self.processes[strategy_id]
            
            # 发送终止信号
            logger.info(f"正在停止策略进程 {strategy_id}，PID: {process.pid}")
            process.terminate()
            
            # 等待进程退出
            process.join(timeout=timeout)
            
            # 如果进程仍在运行，强制终止
            if process.is_alive():
                logger.warning(f"策略进程 {strategy_id} 未在超时时间内退出，强制终止")
                process.kill()
                process.join()
            
            # 清理资源
            del self.processes[strategy_id]
            if strategy_id in self.process_queues:
                del self.process_queues[strategy_id]
            if strategy_id in self.main_to_process_queues:
                del self.main_to_process_queues[strategy_id]
            if strategy_id in self.process_to_main_queues:
                del self.process_to_main_queues[strategy_id]
            if strategy_id in self.shared_locks:
                del self.shared_locks[strategy_id]
            if strategy_id in self.shared_events:
                del self.shared_events[strategy_id]
            # 清理共享状态（使用已存在的锁）
            if strategy_id in self.shared_locks:
                with self.shared_locks[strategy_id]:
                    keys_to_remove = [k for k in list(self.shared_state.keys()) if k.startswith(f'{strategy_id}_')]
                    for key in keys_to_remove:
                        if key in self.shared_state:
                            del self.shared_state[key]
            else:
                # 如果没有锁，直接清理（可能锁已被删除）
                keys_to_remove = [k for k in list(self.shared_state.keys()) if k.startswith(f'{strategy_id}_')]
                for key in keys_to_remove:
                    if key in self.shared_state:
                        del self.shared_state[key]
            if strategy_id in self.process_status:
                self.process_status[strategy_id]['status'] = 'stopped'
            
            logger.info(f"策略进程 {strategy_id} 已停止")
            return True
            
        except Exception as e:
            logger.error(f"停止策略进程 {strategy_id} 失败: {e}")
            return False
    
    def send_message_to_process(self, strategy_id: str, message: Dict[str, Any]) -> bool:
        """
        向策略进程发送消息
        
        Args:
            strategy_id: 策略唯一标识
            message: 消息字典
            
        Returns:
            bool: 是否成功发送
        """
        if strategy_id not in self.main_to_process_queues:
            logger.warning(f"策略进程 {strategy_id} 的通信队列不存在")
            return False
        
        try:
            # 使用双向队列发送消息，避免死锁
            self.main_to_process_queues[strategy_id].put(message, block=False)
            return True
        except Exception as e:
            logger.error(f"向策略进程 {strategy_id} 发送消息失败: {e}")
            return False
    
    def send_message_to_process_sync(
        self, 
        strategy_id: str, 
        message: Dict[str, Any], 
        timeout: float = 5.0
    ) -> bool:
        """
        同步向策略进程发送消息并等待响应
        
        Args:
            strategy_id: 策略唯一标识
            message: 消息字典
            timeout: 超时时间（秒）
            
        Returns:
            bool: 是否成功发送并收到响应
        """
        if not self.send_message_to_process(strategy_id, message):
            return False
        
        # 等待响应
        response = self.receive_message_from_process(strategy_id, timeout=timeout)
        return response is not None and response.get('type') == 'ack'
    
    def receive_message_from_process(self, strategy_id: str, timeout: float = 0.1) -> Optional[Dict[str, Any]]:
        """
        从策略进程接收消息
        
        Args:
            strategy_id: 策略唯一标识
            timeout: 接收超时时间（秒）
            
        Returns:
            Optional[Dict[str, Any]]: 消息字典，超时返回None
        """
        if strategy_id not in self.process_to_main_queues:
            return None
        
        try:
            return self.process_to_main_queues[strategy_id].get(timeout=timeout)
        except Empty:
            return None
        except Exception as e:
            logger.error(f"从策略进程 {strategy_id} 接收消息失败: {e}")
            return None
    
    def get_shared_state(self, strategy_id: str, key: str) -> Any:
        """
        获取共享状态值（线程安全）
        
        Args:
            strategy_id: 策略唯一标识
            key: 状态键名
            
        Returns:
            Any: 状态值
        """
        full_key = f'{strategy_id}_{key}'
        if strategy_id in self.shared_locks:
            with self.shared_locks[strategy_id]:
                return self.shared_state.get(full_key)
        return self.shared_state.get(full_key)
    
    def set_shared_state(self, strategy_id: str, key: str, value: Any) -> None:
        """
        设置共享状态值（线程安全）
        
        Args:
            strategy_id: 策略唯一标识
            key: 状态键名
            value: 状态值
        """
        full_key = f'{strategy_id}_{key}'
        if strategy_id in self.shared_locks:
            with self.shared_locks[strategy_id]:
                self.shared_state[full_key] = value
        else:
            self.shared_state[full_key] = value
    
    def wait_for_process_event(self, strategy_id: str, timeout: Optional[float] = None) -> bool:
        """
        等待进程事件（用于同步）
        
        Args:
            strategy_id: 策略唯一标识
            timeout: 超时时间（秒），None表示无限等待
            
        Returns:
            bool: 是否等到事件
        """
        if strategy_id not in self.shared_events:
            return False
        
        return self.shared_events[strategy_id].wait(timeout=timeout)
    
    def set_process_event(self, strategy_id: str) -> None:
        """
        设置进程事件（用于通知）
        
        Args:
            strategy_id: 策略唯一标识
        """
        if strategy_id in self.shared_events:
            self.shared_events[strategy_id].set()
    
    def clear_process_event(self, strategy_id: str) -> None:
        """
        清除进程事件
        
        Args:
            strategy_id: 策略唯一标识
        """
        if strategy_id in self.shared_events:
            self.shared_events[strategy_id].clear()
    
    def start_monitoring(self) -> None:
        """启动进程监控线程"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = Thread(target=self._monitor_processes, daemon=True)
        self.monitor_thread.start()
        logger.info("进程监控线程已启动")
    
    def _monitor_processes(self) -> None:
        """监控进程状态"""
        while self.monitoring:
            try:
                # 检查所有进程状态
                for strategy_id, process in list(self.processes.items()):
                    if not process.is_alive():
                        # 进程异常退出
                        exit_code = process.exitcode
                        logger.warning(
                            f"策略进程 {strategy_id} 异常退出，退出码: {exit_code}"
                        )
                        
                        # 更新状态
                        if strategy_id in self.process_status:
                            self.process_status[strategy_id]['status'] = 'crashed'
                            self.process_status[strategy_id]['exit_code'] = exit_code
                        
                        # 清理资源
                        if strategy_id in self.process_queues:
                            del self.process_queues[strategy_id]
                        del self.processes[strategy_id]
                
                # 接收进程消息（避免阻塞，使用非阻塞方式）
                for strategy_id in list(self.process_to_main_queues.keys()):
                    try:
                        message = self.process_to_main_queues[strategy_id].get_nowait()
                        if message:
                            self._handle_process_message(strategy_id, message)
                    except Empty:
                        pass
                    except Exception as e:
                        logger.error(f"接收进程 {strategy_id} 消息异常: {e}")
                
                # 休眠一段时间
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"进程监控异常: {e}")
                time.sleep(1)
    
    def _handle_process_message(self, strategy_id: str, message: Dict[str, Any]) -> None:
        """处理进程消息"""
        msg_type = message.get('type')
        
        if msg_type == 'started':
            logger.info(f"策略进程 {strategy_id} 已启动")
            if strategy_id in self.process_status:
                self.process_status[strategy_id]['status'] = 'running'
        
        elif msg_type == 'completed':
            logger.info(f"策略进程 {strategy_id} 执行完成")
            if strategy_id in self.process_status:
                self.process_status[strategy_id]['status'] = 'completed'
        
        elif msg_type == 'error':
            logger.error(
                f"策略进程 {strategy_id} 执行错误: {message.get('error')}"
            )
            if strategy_id in self.process_status:
                self.process_status[strategy_id]['status'] = 'error'
                self.process_status[strategy_id]['error'] = message.get('error')
        
        elif msg_type == 'interrupted':
            logger.info(f"策略进程 {strategy_id} 被中断")
            if strategy_id in self.process_status:
                self.process_status[strategy_id]['status'] = 'interrupted'
    
    def get_process_status(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """
        获取进程状态
        
        Args:
            strategy_id: 策略唯一标识
            
        Returns:
            Optional[Dict[str, Any]]: 进程状态字典
        """
        return self.process_status.get(strategy_id)
    
    def get_all_process_status(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有进程状态
        
        Returns:
            Dict[str, Dict[str, Any]]: 所有进程状态字典
        """
        return dict(self.process_status)
    
    def stop_all_processes(self) -> None:
        """停止所有策略进程"""
        logger.info("正在停止所有策略进程...")
        for strategy_id in list(self.processes.keys()):
            self.stop_strategy_process(strategy_id)
        logger.info("所有策略进程已停止")
    
    def close(self) -> None:
        """关闭进程管理器"""
        logger.info("正在关闭进程管理器...")
        
        # 停止监控
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
        
        # 停止所有进程
        self.stop_all_processes()
        
        # 关闭共享状态管理器
        self.manager.shutdown()
        
        logger.info("进程管理器已关闭")
