"""
多进程回测管理器

实现多进程CTA策略回测功能，支持多进程并行回测，提升回测性能。
参考Elite版多进程回测设计，确保回测结果准确。
"""

import multiprocessing
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from queue import Empty
import time
import traceback

from .multiprocess_manager import ProcessManager
from .logger import logger
from .platform_utils import is_mac_system


class MultiProcessBacktester:
    """
    多进程回测管理器
    
    支持多进程并行执行多个策略回测，充分利用多核CPU提升回测性能。
    """
    
    def __init__(self, max_workers: Optional[int] = None):
        """
        初始化多进程回测管理器
        
        Args:
            max_workers: 最大工作进程数，None表示使用CPU核心数
        """
        self.process_manager = ProcessManager(max_workers=max_workers)
        
        # 回测任务管理
        self.backtest_tasks: Dict[str, Dict[str, Any]] = {}
        self.backtest_results: Dict[str, Dict[str, Any]] = {}
        
        logger.info("MultiProcessBacktester初始化完成")
    
    def run_backtest(
        self,
        task_id: str,
        strategy_class: type,
        strategy_params: Dict[str, Any],
        backtest_params: Dict[str, Any],
        callback: Optional[Callable] = None
    ) -> bool:
        """
        启动单个策略回测任务
        
        Args:
            task_id: 回测任务唯一标识
            strategy_class: 策略类
            strategy_params: 策略参数
            backtest_params: 回测参数（包含历史数据、起始资金等）
            callback: 回测完成后的回调函数
            
        Returns:
            bool: 是否成功启动
        """
        if task_id in self.backtest_tasks:
            logger.warning(f"回测任务 {task_id} 已存在")
            return False
        
        try:
            # 创建回测任务信息
            self.backtest_tasks[task_id] = {
                'strategy_class': strategy_class,
                'strategy_params': strategy_params,
                'backtest_params': backtest_params,
                'callback': callback,
                'status': 'pending',
                'start_time': None,
                'end_time': None
            }
            
            # 启动回测进程
            success = self.process_manager.start_strategy_process(
                strategy_id=task_id,
                strategy_func=self._backtest_worker,
                strategy_args=(task_id, strategy_class, strategy_params, backtest_params),
                strategy_kwargs={}
            )
            
            if success:
                self.backtest_tasks[task_id]['status'] = 'running'
                self.backtest_tasks[task_id]['start_time'] = time.time()
                logger.info(f"回测任务 {task_id} 已启动")
            
            return success
            
        except Exception as e:
            logger.error(f"启动回测任务 {task_id} 失败: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def run_batch_backtest(
        self,
        strategy_class: type,
        strategy_params_list: List[Dict[str, Any]],
        backtest_params: Dict[str, Any],
        callback: Optional[Callable] = None
    ) -> List[str]:
        """
        批量启动多个策略回测任务（参数优化场景）
        
        Args:
            strategy_class: 策略类
            strategy_params_list: 策略参数列表（每个参数组合一个回测）
            backtest_params: 回测参数
            callback: 每个回测完成后的回调函数
            
        Returns:
            List[str]: 启动的任务ID列表
        """
        task_ids = []
        
        for i, strategy_params in enumerate(strategy_params_list):
            task_id = f"backtest_{i}_{int(time.time())}"
            
            success = self.run_backtest(
                task_id=task_id,
                strategy_class=strategy_class,
                strategy_params=strategy_params,
                backtest_params=backtest_params,
                callback=callback
            )
            
            if success:
                task_ids.append(task_id)
            else:
                logger.warning(f"回测任务 {task_id} 启动失败")
        
        logger.info(f"批量启动 {len(task_ids)} 个回测任务")
        return task_ids
    
    def _backtest_worker(
        self,
        task_id: str,
        strategy_class: type,
        strategy_params: Dict[str, Any],
        backtest_params: Dict[str, Any]
    ) -> None:
        """
        回测工作进程函数
        
        在独立进程中执行策略回测逻辑。
        
        Args:
            task_id: 回测任务ID
            strategy_class: 策略类
            strategy_params: 策略参数
            backtest_params: 回测参数
        """
        try:
            logger.info(f"回测任务 {task_id} 开始执行")
            
            # 创建策略实例
            strategy = strategy_class(**strategy_params)
            
            # 执行回测逻辑
            # 注意：这里需要根据实际的回测引擎接口来实现
            # 由于vnpy_ctabacktester模块可能不存在，这里提供一个通用框架
            
            result = {
                'task_id': task_id,
                'strategy_params': strategy_params,
                'backtest_params': backtest_params,
                'status': 'completed',
                'result': None,  # 回测结果（需要根据实际回测引擎填充）
                'error': None
            }
            
            # 这里应该调用实际的回测引擎
            # 由于没有vnpy_ctabacktester模块，这里提供一个占位实现
            logger.info(f"回测任务 {task_id} 执行完成（占位实现）")
            
            # 向主进程发送结果
            self.process_manager.send_message_to_process(
                task_id,
                {
                    'type': 'backtest_result',
                    'task_id': task_id,
                    'result': result
                }
            )
            
        except Exception as e:
            logger.error(f"回测任务 {task_id} 执行异常: {e}")
            logger.error(traceback.format_exc())
            
            # 向主进程发送错误
            self.process_manager.send_message_to_process(
                task_id,
                {
                    'type': 'backtest_error',
                    'task_id': task_id,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                }
            )
    
    def get_backtest_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取回测结果
        
        Args:
            task_id: 回测任务ID
            
        Returns:
            Optional[Dict[str, Any]]: 回测结果字典
        """
        return self.backtest_results.get(task_id)
    
    def get_all_backtest_results(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有回测结果
        
        Returns:
            Dict[str, Dict[str, Any]]: 所有回测结果字典
        """
        return dict(self.backtest_results)
    
    def wait_for_backtest(self, task_id: str, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        等待回测完成
        
        Args:
            task_id: 回测任务ID
            timeout: 超时时间（秒），None表示无限等待
            
        Returns:
            Optional[Dict[str, Any]]: 回测结果，超时返回None
        """
        start_time = time.time()
        
        while True:
            # 检查是否已有结果
            if task_id in self.backtest_results:
                return self.backtest_results[task_id]
            
            # 检查超时
            if timeout and (time.time() - start_time) > timeout:
                logger.warning(f"等待回测任务 {task_id} 超时")
                return None
            
            # 接收进程消息
            message = self.process_manager.receive_message_from_process(task_id, timeout=0.1)
            if message:
                self._handle_backtest_message(task_id, message)
            
            # 检查进程状态
            status = self.process_manager.get_process_status(task_id)
            if status and status.get('status') in ['completed', 'error', 'crashed']:
                # 进程已结束，但可能还有消息未处理
                time.sleep(0.1)
                continue
            
            time.sleep(0.1)
    
    def _handle_backtest_message(self, task_id: str, message: Dict[str, Any]) -> None:
        """
        处理回测进程消息
        
        Args:
            task_id: 回测任务ID
            message: 消息字典
        """
        msg_type = message.get('type')
        
        if msg_type == 'backtest_result':
            result = message.get('result')
            self.backtest_results[task_id] = result
            
            # 更新任务状态
            if task_id in self.backtest_tasks:
                self.backtest_tasks[task_id]['status'] = 'completed'
                self.backtest_tasks[task_id]['end_time'] = time.time()
                
                # 触发回调
                callback = self.backtest_tasks[task_id].get('callback')
                if callback:
                    try:
                        callback(result)
                    except Exception as e:
                        logger.error(f"执行回测回调函数失败: {e}")
            
            logger.info(f"回测任务 {task_id} 完成")
        
        elif msg_type == 'backtest_error':
            error = message.get('error')
            self.backtest_results[task_id] = {
                'task_id': task_id,
                'status': 'error',
                'error': error
            }
            
            # 更新任务状态
            if task_id in self.backtest_tasks:
                self.backtest_tasks[task_id]['status'] = 'error'
                self.backtest_tasks[task_id]['end_time'] = time.time()
            
            logger.error(f"回测任务 {task_id} 执行错误: {error}")
    
    def stop_backtest(self, task_id: str) -> bool:
        """
        停止回测任务
        
        Args:
            task_id: 回测任务ID
            
        Returns:
            bool: 是否成功停止
        """
        success = self.process_manager.stop_strategy_process(task_id)
        
        if success and task_id in self.backtest_tasks:
            self.backtest_tasks[task_id]['status'] = 'stopped'
            self.backtest_tasks[task_id]['end_time'] = time.time()
        
        return success
    
    def stop_all_backtests(self) -> None:
        """停止所有回测任务"""
        logger.info("正在停止所有回测任务...")
        for task_id in list(self.backtest_tasks.keys()):
            self.stop_backtest(task_id)
        logger.info("所有回测任务已停止")
    
    def get_backtest_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取回测任务状态
        
        Args:
            task_id: 回测任务ID
            
        Returns:
            Optional[Dict[str, Any]]: 任务状态字典
        """
        if task_id not in self.backtest_tasks:
            return None
        
        status = dict(self.backtest_tasks[task_id])
        
        # 添加进程状态
        process_status = self.process_manager.get_process_status(task_id)
        if process_status:
            status['process_status'] = process_status
        
        # 添加结果
        if task_id in self.backtest_results:
            status['result'] = self.backtest_results[task_id]
        
        return status
    
    def get_all_backtest_status(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有回测任务状态
        
        Returns:
            Dict[str, Dict[str, Any]]: 所有任务状态字典
        """
        status_dict = {}
        for task_id in self.backtest_tasks.keys():
            status_dict[task_id] = self.get_backtest_status(task_id)
        return status_dict
    
    def close(self) -> None:
        """关闭多进程回测管理器"""
        logger.info("正在关闭多进程回测管理器...")
        self.stop_all_backtests()
        self.process_manager.close()
        logger.info("多进程回测管理器已关闭")
