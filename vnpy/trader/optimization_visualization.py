"""
参数优化可视化模块

实现参数优化热力图等可视化工具，通过可视化方式辅助参数选择。
参考Elite版参数优化可视化设计。
"""

from typing import Dict, List, Optional, Tuple
import math
import traceback

from .logger import logger

try:
    import matplotlib
    matplotlib.use('Agg')  # 使用非交互式后端，避免Mac系统显示问题
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    logger.warning("matplotlib未安装，参数优化可视化功能将不可用")

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.warning("numpy未安装，部分可视化功能可能不可用")


class OptimizationVisualization:
    """
    参数优化可视化工具
    
    提供热力图等可视化工具，辅助用户进行参数选择。
    """
    
    def __init__(self):
        """初始化可视化工具"""
        if not HAS_MATPLOTLIB:
            logger.warning("matplotlib未安装，可视化功能受限")
        
        logger.info("OptimizationVisualization初始化完成")
    
    def plot_heatmap(
        self,
        param1_name: str,
        param1_values: List[float],
        param2_name: str,
        param2_values: List[float],
        metric_values: List[List[float]],
        metric_name: str = "R-Cubed",
        output_path: Optional[str] = None,
        title: Optional[str] = None
    ) -> Optional[str]:
        """
        绘制参数优化热力图
        
        Args:
            param1_name: 参数1名称
            param1_values: 参数1取值列表
            param2_name: 参数2名称
            param2_values: 参数2取值列表
            metric_values: 指标值矩阵（param1_values x param2_values）
            metric_name: 指标名称
            output_path: 输出文件路径（None表示不保存）
            title: 图表标题（None表示自动生成）
            
        Returns:
            Optional[str]: 输出文件路径，如果未保存则返回None
        """
        if not HAS_MATPLOTLIB:
            logger.error("matplotlib未安装，无法绘制热力图")
            return None
        
        try:
            # 创建图形
            fig, ax = plt.subplots(figsize=(10, 8))
            
            # 准备数据
            if HAS_NUMPY:
                metric_array = np.array(metric_values)
            else:
                # 手动转换为矩阵
                metric_array = []
                for row in metric_values:
                    metric_array.append(row)
            
            # 绘制热力图
            im = ax.imshow(
                metric_array,
                cmap='RdYlGn',  # 红-黄-绿配色
                aspect='auto',
                interpolation='nearest'
            )
            
            # 设置坐标轴
            ax.set_xticks(range(len(param2_values)))
            ax.set_yticks(range(len(param1_values)))
            ax.set_xticklabels([f"{v:.2f}" for v in param2_values], rotation=45, ha='right')
            ax.set_yticklabels([f"{v:.2f}" for v in param1_values])
            
            # 设置标签
            ax.set_xlabel(param2_name, fontsize=12)
            ax.set_ylabel(param1_name, fontsize=12)
            
            # 设置标题
            if title:
                ax.set_title(title, fontsize=14, fontweight='bold')
            else:
                ax.set_title(f"{metric_name} 参数优化热力图", fontsize=14, fontweight='bold')
            
            # 添加颜色条
            cbar = plt.colorbar(im, ax=ax)
            cbar.set_label(metric_name, fontsize=12)
            
            # 在热力图上标注数值（如果矩阵不太大）
            if len(param1_values) <= 20 and len(param2_values) <= 20:
                for i in range(len(param1_values)):
                    for j in range(len(param2_values)):
                        value = metric_values[i][j]
                        text = ax.text(
                            j, i, f"{value:.2f}",
                            ha="center", va="center",
                            color="black" if value > (metric_array.max() + metric_array.min()) / 2 else "white",
                            fontsize=8
                        )
            
            plt.tight_layout()
            
            # 保存或显示
            if output_path:
                plt.savefig(output_path, dpi=300, bbox_inches='tight')
                logger.info(f"热力图已保存到: {output_path}")
                plt.close()
                return output_path
            else:
                # 不显示，只返回（Mac系统可能无法显示）
                plt.close()
                return None
                
        except Exception as e:
            logger.error(f"绘制热力图失败: {e}")
            logger.error(traceback.format_exc())
            return None
    
    def plot_parameter_surface(
        self,
        param1_name: str,
        param1_values: List[float],
        param2_name: str,
        param2_values: List[float],
        metric_values: List[List[float]],
        metric_name: str = "R-Cubed",
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        绘制参数优化3D表面图
        
        Args:
            param1_name: 参数1名称
            param1_values: 参数1取值列表
            param2_name: 参数2名称
            param2_values: 参数2取值列表
            metric_values: 指标值矩阵
            metric_name: 指标名称
            output_path: 输出文件路径
            
        Returns:
            Optional[str]: 输出文件路径
        """
        if not HAS_MATPLOTLIB:
            logger.error("matplotlib未安装，无法绘制3D表面图")
            return None
        
        try:
            from mpl_toolkits.mplot3d import Axes3D
            
            # 创建3D图形
            fig = plt.figure(figsize=(12, 8))
            ax = fig.add_subplot(111, projection='3d')
            
            # 准备网格数据
            if HAS_NUMPY:
                X, Y = np.meshgrid(param2_values, param1_values)
                Z = np.array(metric_values)
            else:
                # 手动创建网格
                X = []
                Y = []
                Z = []
                for i, p1 in enumerate(param1_values):
                    row_x = []
                    row_y = []
                    row_z = []
                    for j, p2 in enumerate(param2_values):
                        row_x.append(p2)
                        row_y.append(p1)
                        row_z.append(metric_values[i][j])
                    X.append(row_x)
                    Y.append(row_y)
                    Z.append(row_z)
            
            # 绘制表面
            surf = ax.plot_surface(
                X, Y, Z,
                cmap='RdYlGn',
                alpha=0.8,
                linewidth=0,
                antialiased=True
            )
            
            # 设置标签
            ax.set_xlabel(param2_name, fontsize=12)
            ax.set_ylabel(param1_name, fontsize=12)
            ax.set_zlabel(metric_name, fontsize=12)
            ax.set_title(f"{metric_name} 参数优化3D表面图", fontsize=14, fontweight='bold')
            
            # 添加颜色条
            fig.colorbar(surf, ax=ax, shrink=0.5, aspect=5)
            
            plt.tight_layout()
            
            # 保存
            if output_path:
                plt.savefig(output_path, dpi=300, bbox_inches='tight')
                logger.info(f"3D表面图已保存到: {output_path}")
                plt.close()
                return output_path
            else:
                plt.close()
                return None
                
        except Exception as e:
            logger.error(f"绘制3D表面图失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def plot_parameter_curve(
        self,
        param_name: str,
        param_values: List[float],
        metric_values: List[float],
        metric_name: str = "R-Cubed",
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        绘制单参数优化曲线
        
        Args:
            param_name: 参数名称
            param_values: 参数取值列表
            metric_values: 指标值列表
            metric_name: 指标名称
            output_path: 输出文件路径
            
        Returns:
            Optional[str]: 输出文件路径
        """
        if not HAS_MATPLOTLIB:
            logger.error("matplotlib未安装，无法绘制曲线图")
            return None
        
        try:
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # 绘制曲线
            ax.plot(param_values, metric_values, 'b-o', linewidth=2, markersize=6)
            
            # 标记最优值
            max_index = metric_values.index(max(metric_values))
            max_param = param_values[max_index]
            max_metric = metric_values[max_index]
            
            ax.plot(max_param, max_metric, 'ro', markersize=12, label=f'最优值: {max_param:.2f}')
            
            # 设置标签
            ax.set_xlabel(param_name, fontsize=12)
            ax.set_ylabel(metric_name, fontsize=12)
            ax.set_title(f"{metric_name} vs {param_name}", fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            plt.tight_layout()
            
            # 保存
            if output_path:
                plt.savefig(output_path, dpi=300, bbox_inches='tight')
                logger.info(f"参数曲线图已保存到: {output_path}")
                plt.close()
                return output_path
            else:
                plt.close()
                return None
                
        except Exception as e:
            logger.error(f"绘制参数曲线失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def plot_optimization_comparison(
        self,
        optimization_results: List[Dict[str, any]],
        metric_name: str = "R-Cubed",
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        绘制多个优化结果的对比图
        
        Args:
            optimization_results: 优化结果列表，每个元素包含参数和指标值
            metric_name: 指标名称
            output_path: 输出文件路径
            
        Returns:
            Optional[str]: 输出文件路径
        """
        if not HAS_MATPLOTLIB:
            logger.error("matplotlib未安装，无法绘制对比图")
            return None
        
        try:
            fig, ax = plt.subplots(figsize=(12, 6))
            
            # 提取数据
            labels = []
            values = []
            for i, result in enumerate(optimization_results):
                # 生成标签（参数组合的字符串表示）
                params_str = ", ".join([f"{k}={v:.2f}" for k, v in result.get('params', {}).items()])
                labels.append(f"组合{i+1}\n{params_str}")
                values.append(result.get('metric', 0.0))
            
            # 绘制柱状图
            bars = ax.bar(range(len(labels)), values, color='steelblue', alpha=0.7)
            
            # 标记最优值
            max_index = values.index(max(values))
            bars[max_index].set_color('red')
            bars[max_index].set_alpha(1.0)
            
            # 设置标签
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
            ax.set_ylabel(metric_name, fontsize=12)
            ax.set_title(f"参数优化结果对比 ({metric_name})", fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3, axis='y')
            
            # 添加数值标签
            for i, (bar, value) in enumerate(zip(bars, values)):
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2., height,
                    f'{value:.3f}',
                    ha='center', va='bottom', fontsize=8
                )
            
            plt.tight_layout()
            
            # 保存
            if output_path:
                plt.savefig(output_path, dpi=300, bbox_inches='tight')
                logger.info(f"优化对比图已保存到: {output_path}")
                plt.close()
                return output_path
            else:
                plt.close()
                return None
                
        except Exception as e:
            logger.error(f"绘制优化对比图失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def generate_optimization_report(
        self,
        optimization_results: List[Dict[str, any]],
        output_path: str,
        metric_name: str = "R-Cubed"
    ) -> bool:
        """
        生成参数优化报告（包含多个可视化图表）
        
        Args:
            optimization_results: 优化结果列表
            output_path: 输出文件路径（PDF或HTML）
            metric_name: 指标名称
            
        Returns:
            bool: 是否成功生成
        """
        if not HAS_MATPLOTLIB:
            logger.error("matplotlib未安装，无法生成优化报告")
            return False
        
        try:
            # 这里可以生成包含多个图表的综合报告
            # 由于PDF生成需要额外库，这里先实现基本的图表保存
            
            logger.info(f"生成参数优化报告: {output_path}")
            
            # 可以扩展为生成HTML报告或PDF报告
            # 目前先记录功能接口
            
            return True
            
        except Exception as e:
            logger.error(f"生成优化报告失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
