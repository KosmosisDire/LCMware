"""LCM Manager singleton for centralized LCM instance management"""

import lcm
import threading
import atexit
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def build_messages(path: str) -> None:
    """Build all LCM messages from the specified path"""
    
    import subprocess, os
    
    # Construct the bash command
    bash_command = f'lcm-gen --lazy --python --ppath "./" "{os.path.join("./", path)}/"*.lcm'
    
    try:
        subprocess.run(bash_command, shell=True, check=True)
        logger.info(f"LCM messages built successfully from {path}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to build LCM messages from {path}: {e}\nEnsure lcm-gen is installed and in PATH.")


class LCMManager:
    """Singleton manager for LCM instance to ensure single shared instance across all clients/servers"""
    
    _instance: Optional['LCMManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the LCM instance and setup cleanup"""
        self._lcm = lcm.LCM()
        self._handler_threads = []
        self._running = False
        self._handler_lock = threading.Lock()
        
        # Register cleanup on exit
        atexit.register(self.shutdown)
        
        logger.info("LCMManager initialized")
    
    @property
    def lcm(self) -> lcm.LCM:
        """Get the shared LCM instance"""
        return self._lcm
    
    def start_handler_thread(self) -> None:
        """Start a background thread for handling LCM messages if not already running"""
        with self._handler_lock:
            if not self._running:
                self._running = True
                handler_thread = threading.Thread(target=self._handle_loop, daemon=True)
                handler_thread.start()
                self._handler_threads.append(handler_thread)
                logger.info("LCM handler thread started")
    
    def stop_handler_threads(self) -> None:
        """Stop all handler threads"""
        with self._handler_lock:
            if self._running:
                self._running = False
                logger.info("Stopping LCM handler threads...")
                for thread in self._handler_threads:
                    if thread.is_alive():
                        thread.join(timeout=1.0)
                self._handler_threads.clear()
                logger.info("LCM handler threads stopped")
    
    def _handle_loop(self):
        """Main LCM message handling loop"""
        while self._running:
            try:
                self._lcm.handle_timeout(100)  # 100ms timeout
            except Exception as e:
                logger.error(f"Error in LCM handler loop: {e}")
                break
    
    def shutdown(self):
        """Shutdown the LCM manager and cleanup resources"""
        logger.info("Shutting down LCMManager...")
        self.stop_handler_threads()
        
        # Reset singleton instance
        with self._lock:
            LCMManager._instance = None
        
        logger.info("LCMManager shutdown complete")
    
    @classmethod
    def get_instance(cls) -> 'LCMManager':
        """Get the singleton instance"""
        return cls()


def get_lcm() -> lcm.LCM:
    """Convenience function to get the shared LCM instance"""
    return LCMManager.get_instance().lcm


def start_lcm_handler() -> None:
    """Convenience function to start the LCM handler thread"""
    LCMManager.get_instance().start_handler_thread()


def stop_lcm_handler() -> None:
    """Convenience function to stop LCM handler threads"""
    LCMManager.get_instance().stop_handler_threads()