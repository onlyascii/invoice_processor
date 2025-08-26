"""System resource monitoring utilities."""

import psutil
from typing import Dict, Any


class SystemMonitor:
    """A class to monitor system resources."""

    @staticmethod
    def get_system_stats() -> Dict[str, Any]:
        """
        Get current system resource usage.

        Returns:
            Dictionary containing system statistics
        """
        process = psutil.Process()

        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=None)

        # Memory usage
        memory = psutil.virtual_memory()
        process_memory = process.memory_info()

        # GPU memory (if available)
        gpu_info = SystemMonitor._get_gpu_info()

        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_used_gb": memory.used / (1024**3),
            "memory_total_gb": memory.total / (1024**3),
            "process_memory_mb": process_memory.rss / (1024**2),
            "gpu_memory": gpu_info
        }

    @staticmethod
    def _get_gpu_info() -> str:
        """
        Get GPU memory information if available.

        Returns:
            GPU memory info string or fallback message
        """
        # Try GPUtil first
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]  # Get first GPU
                return f"{gpu.memoryUsed}MB/{gpu.memoryTotal}MB ({gpu.memoryUtil*100:.1f}%)"
        except ImportError:
            pass

        # Try nvidia-ml-py as alternative
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            gpu_memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
            used_mb = gpu_memory.used // 1024 // 1024
            total_mb = gpu_memory.total // 1024 // 1024
            usage_percent = (gpu_memory.used / gpu_memory.total) * 100
            return f"{used_mb}MB/{total_mb}MB ({usage_percent:.1f}%)"
        except:
            pass

        return "No GPU"

    @staticmethod
    def format_stats_for_display(stats: Dict[str, Any]) -> str:
        """
        Format system stats for display in UI.

        Args:
            stats: System statistics dictionary

        Returns:
            Formatted stats string
        """
        return (
            f"CPU: {stats['cpu_percent']:.1f}% | "
            f"Memory: {stats['memory_percent']:.1f}% "
            f"({stats['memory_used_gb']:.1f}GB/{stats['memory_total_gb']:.1f}GB) | "
            f"Process: {stats['process_memory_mb']:.1f}MB | "
            f"GPU: {stats['gpu_memory']}"
        )
