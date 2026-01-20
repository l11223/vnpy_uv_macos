"""
优化指标模块

实现R-Cubed稳健优化指标计算，提供比传统夏普比率更能代表长期收益的指标。
参考Elite版R-Cubed指标设计，减少过度拟合风险。
"""

from typing import List, Dict, Optional
import math
from collections import defaultdict

from .logger import logger

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.warning("numpy未安装，部分优化指标计算可能不可用")


class OptimizationMetrics:
    """
    优化指标计算器
    
    提供多种策略优化指标，包括R-Cubed稳健指标、夏普比率等。
    """
    
    def __init__(self):
        """初始化优化指标计算器"""
        logger.info("OptimizationMetrics初始化完成")
    
    def calculate_sharpe_ratio(
        self,
        returns: List[float],
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252
    ) -> float:
        """
        计算夏普比率
        
        Args:
            returns: 收益率列表
            risk_free_rate: 无风险利率（年化）
            periods_per_year: 每年交易周期数（默认252个交易日）
            
        Returns:
            float: 夏普比率
        """
        if not returns or len(returns) == 0:
            return 0.0
        
        if HAS_NUMPY:
            returns_array = np.array(returns)
            mean_return = np.mean(returns_array)
            std_return = np.std(returns_array, ddof=1)
        else:
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
            std_return = math.sqrt(variance)
        
        if std_return == 0:
            return 0.0
        
        # 年化收益率和波动率
        annual_return = mean_return * periods_per_year
        annual_std = std_return * math.sqrt(periods_per_year)
        
        # 夏普比率 = (年化收益率 - 无风险利率) / 年化波动率
        sharpe = (annual_return - risk_free_rate) / annual_std
        
        return sharpe
    
    def calculate_sortino_ratio(
        self,
        returns: List[float],
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252
    ) -> float:
        """
        计算Sortino比率（只考虑下行波动）
        
        Args:
            returns: 收益率列表
            risk_free_rate: 无风险利率（年化）
            periods_per_year: 每年交易周期数
            
        Returns:
            float: Sortino比率
        """
        if not returns or len(returns) == 0:
            return 0.0
        
        if HAS_NUMPY:
            returns_array = np.array(returns)
            mean_return = np.mean(returns_array)
            # 只计算负收益的标准差（下行波动）
            negative_returns = returns_array[returns_array < 0]
            if len(negative_returns) == 0:
                return float('inf') if mean_return > risk_free_rate else 0.0
            downside_std = np.std(negative_returns, ddof=1)
        else:
            mean_return = sum(returns) / len(returns)
            negative_returns = [r for r in returns if r < 0]
            if len(negative_returns) == 0:
                return float('inf') if mean_return > risk_free_rate else 0.0
            variance = sum((r - mean_return) ** 2 for r in negative_returns) / (len(negative_returns) - 1)
            downside_std = math.sqrt(variance)
        
        if downside_std == 0:
            return float('inf') if mean_return > risk_free_rate else 0.0
        
        # 年化
        annual_return = mean_return * periods_per_year
        annual_downside_std = downside_std * math.sqrt(periods_per_year)
        
        sortino = (annual_return - risk_free_rate) / annual_downside_std
        
        return sortino
    
    def calculate_r_cubed(
        self,
        returns: List[float],
        periods_per_year: int = 252,
        alpha: float = 0.5
    ) -> float:
        """
        计算R-Cubed稳健优化指标
        
        R-Cubed是一个稳健的优化指标，比传统夏普比率更能代表长期收益，
        减少过度拟合风险。公式基于收益率的稳健统计量。
        
        Args:
            returns: 收益率列表
            periods_per_year: 每年交易周期数（默认252个交易日）
            alpha: 稳健性参数（0-1之间，默认0.5）
            
        Returns:
            float: R-Cubed指标值
        """
        if not returns or len(returns) == 0:
            return 0.0
        
        if HAS_NUMPY:
            returns_array = np.array(returns)
            
            # 计算稳健的收益率统计量
            # 使用中位数和MAD（中位数绝对偏差）代替均值和标准差
            median_return = np.median(returns_array)
            
            # MAD (Median Absolute Deviation)
            mad = np.median(np.abs(returns_array - median_return))
            
            # 稳健的年化收益率（使用中位数）
            annual_median_return = median_return * periods_per_year
            
            # 稳健的年化波动率（使用MAD，转换为标准差近似）
            # MAD ≈ 0.6745 * 标准差（对于正态分布）
            if mad > 0:
                robust_std = mad / 0.6745
                annual_robust_std = robust_std * math.sqrt(periods_per_year)
            else:
                annual_robust_std = 0.001  # 避免除零
            
            # R-Cubed公式：结合稳健统计量和传统指标
            # R³ = (稳健年化收益) / (稳健年化波动) * (1 - alpha) + (传统夏普) * alpha
            traditional_sharpe = self.calculate_sharpe_ratio(returns, 0.0, periods_per_year)
            
            if annual_robust_std > 0:
                robust_ratio = annual_median_return / annual_robust_std
            else:
                robust_ratio = 0.0
            
            # 加权组合
            r_cubed = robust_ratio * (1 - alpha) + traditional_sharpe * alpha
            
        else:
            # 不使用numpy的实现
            sorted_returns = sorted(returns)
            n = len(sorted_returns)
            
            # 中位数
            if n % 2 == 0:
                median_return = (sorted_returns[n//2 - 1] + sorted_returns[n//2]) / 2
            else:
                median_return = sorted_returns[n//2]
            
            # MAD
            deviations = [abs(r - median_return) for r in returns]
            sorted_deviations = sorted(deviations)
            if n % 2 == 0:
                mad = (sorted_deviations[n//2 - 1] + sorted_deviations[n//2]) / 2
            else:
                mad = sorted_deviations[n//2]
            
            # 年化
            annual_median_return = median_return * periods_per_year
            if mad > 0:
                robust_std = mad / 0.6745
                annual_robust_std = robust_std * math.sqrt(periods_per_year)
            else:
                annual_robust_std = 0.001
            
            traditional_sharpe = self.calculate_sharpe_ratio(returns, 0.0, periods_per_year)
            
            if annual_robust_std > 0:
                robust_ratio = annual_median_return / annual_robust_std
            else:
                robust_ratio = 0.0
            
            r_cubed = robust_ratio * (1 - alpha) + traditional_sharpe * alpha
        
        return r_cubed
    
    def calculate_max_drawdown(self, equity_curve: List[float]) -> Dict[str, float]:
        """
        计算最大回撤
        
        Args:
            equity_curve: 权益曲线（账户净值序列）
            
        Returns:
            Dict[str, float]: 包含最大回撤、回撤开始时间、回撤结束时间等信息
        """
        if not equity_curve or len(equity_curve) == 0:
            return {
                'max_drawdown': 0.0,
                'max_drawdown_pct': 0.0,
                'drawdown_start': 0,
                'drawdown_end': 0
            }
        
        max_drawdown = 0.0
        max_drawdown_pct = 0.0
        peak = equity_curve[0]
        peak_index = 0
        drawdown_start = 0
        drawdown_end = 0
        
        for i, value in enumerate(equity_curve):
            if value > peak:
                peak = value
                peak_index = i
            else:
                drawdown = peak - value
                drawdown_pct = drawdown / peak if peak > 0 else 0.0
                
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
                    max_drawdown_pct = drawdown_pct
                    drawdown_start = peak_index
                    drawdown_end = i
        
        return {
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'drawdown_start': drawdown_start,
            'drawdown_end': drawdown_end
        }
    
    def calculate_calmar_ratio(
        self,
        returns: List[float],
        equity_curve: List[float],
        periods_per_year: int = 252
    ) -> float:
        """
        计算Calmar比率（年化收益率 / 最大回撤）
        
        Args:
            returns: 收益率列表
            equity_curve: 权益曲线
            periods_per_year: 每年交易周期数
            
        Returns:
            float: Calmar比率
        """
        if not returns or len(returns) == 0:
            return 0.0
        
        # 年化收益率
        mean_return = sum(returns) / len(returns)
        annual_return = mean_return * periods_per_year
        
        # 最大回撤
        drawdown_info = self.calculate_max_drawdown(equity_curve)
        max_drawdown_pct = drawdown_info['max_drawdown_pct']
        
        if max_drawdown_pct == 0:
            return float('inf') if annual_return > 0 else 0.0
        
        calmar = annual_return / max_drawdown_pct
        
        return calmar
    
    def calculate_win_rate(self, returns: List[float]) -> float:
        """
        计算胜率（盈利交易占比）
        
        Args:
            returns: 收益率列表
            
        Returns:
            float: 胜率（0-1之间）
        """
        if not returns or len(returns) == 0:
            return 0.0
        
        winning_trades = sum(1 for r in returns if r > 0)
        win_rate = winning_trades / len(returns)
        
        return win_rate
    
    def calculate_profit_factor(self, returns: List[float]) -> float:
        """
        计算盈利因子（总盈利 / 总亏损）
        
        Args:
            returns: 收益率列表
            
        Returns:
            float: 盈利因子
        """
        if not returns or len(returns) == 0:
            return 0.0
        
        total_profit = sum(r for r in returns if r > 0)
        total_loss = abs(sum(r for r in returns if r < 0))
        
        if total_loss == 0:
            return float('inf') if total_profit > 0 else 0.0
        
        profit_factor = total_profit / total_loss
        
        return profit_factor
    
    def calculate_all_metrics(
        self,
        returns: List[float],
        equity_curve: Optional[List[float]] = None,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252
    ) -> Dict[str, float]:
        """
        计算所有优化指标
        
        Args:
            returns: 收益率列表
            equity_curve: 权益曲线（可选）
            risk_free_rate: 无风险利率
            periods_per_year: 每年交易周期数
            
        Returns:
            Dict[str, float]: 所有指标字典
        """
        metrics = {
            'sharpe_ratio': self.calculate_sharpe_ratio(returns, risk_free_rate, periods_per_year),
            'sortino_ratio': self.calculate_sortino_ratio(returns, risk_free_rate, periods_per_year),
            'r_cubed': self.calculate_r_cubed(returns, periods_per_year),
            'win_rate': self.calculate_win_rate(returns),
            'profit_factor': self.calculate_profit_factor(returns)
        }
        
        if equity_curve:
            drawdown_info = self.calculate_max_drawdown(equity_curve)
            metrics['max_drawdown'] = drawdown_info['max_drawdown']
            metrics['max_drawdown_pct'] = drawdown_info['max_drawdown_pct']
            metrics['calmar_ratio'] = self.calculate_calmar_ratio(returns, equity_curve, periods_per_year)
        
        return metrics
