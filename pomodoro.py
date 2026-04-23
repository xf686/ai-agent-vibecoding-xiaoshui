#!/usr/bin/env python3
"""命令行番茄钟 Pomodoro Timer"""

import time
import signal
import sys
import argparse
import os
import threading


class PomodoroTimer:
    def __init__(self, work_minutes=25, break_minutes=5, total_tomatoes=4):
        self.work_seconds = work_minutes * 60
        self.break_seconds = break_minutes * 60
        self.total_tomatoes = total_tomatoes
        self.completed_tomatoes = 0
        
        self.current_time = self.work_seconds
        self.is_running = False
        self.is_paused = False
        self.is_work = True  # True=工作, False=休息
        
        self.lock = threading.Lock()
        
    def start(self):
        self.is_running = True
        self.is_paused = False
        self._countdown()
        
    def pause(self):
        with self.lock:
            self.is_paused = not self.is_paused
            
    def stop(self):
        self.is_running = False
        
    def _countdown(self):
        while self.is_running and self.completed_tomatoes < self.total_tomatoes:
            if not self.is_paused:
                self._display()
                time.sleep(1)
                self.current_time -= 1
                
                if self.current_time <= 0:
                    self._switch_phase()
            else:
                time.sleep(0.1)
                
        if self.completed_tomatoes >= self.total_tomatoes:
            self._display()
            print("\n🎉 所有番茄钟完成！")
            self._bell()
            
    def _switch_phase(self):
        if self.is_work:
            # 工作结束
            self.completed_tomatoes += 1
            print(f"\n⏰ 第 {self.completed_tomatoes} 个番茄钟完成！")
            self._bell()
            
            if self.completed_tomatoes < self.total_tomatoes:
                self.is_work = False
                self.current_time = self.break_seconds
                print("➡️  休息一下...")
        else:
            # 休息结束
            self.is_work = True
            self.current_time = self.work_seconds
            print("➡️  开始工作！")
            
    def _display(self):
        minutes = self.current_time // 60
        seconds = self.current_time % 60
        phase = "🔴 工作" if self.is_work else "🟢 休息"
        status = "⏸️" if self.is_paused else "▶️"
        progress = f"[{self.completed_tomatoes}/{self.total_tomatoes}]"
        
        # 清除当前行并显示
        print(f"\r{phase} {status} {progress} {minutes:02d}:{seconds:02d}", end="", flush=True)
        
    def _bell(self):
        # 发出提示音
        print("\a", end="")
        sys.stdout.flush()


def parse_args():
    parser = argparse.ArgumentParser(
        description="命令行番茄钟",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  pomodoro              # 默认 25+5 分钟, 4 个番茄
  pomodoro -w 30        # 工作 30 分钟
  pomodoro -w 25 -b 10  # 工作 25, 休息 10 分钟
  pomodoro -t 2         # 2 个番茄
        """
    )
    parser.add_argument("-w", "--work", type=int, default=25, help="工作时长(分钟)")
    parser.add_argument("-b", "--break", dest="break_time", type=int, default=5, help="休息时长(分钟)")
    parser.add_argument("-t", "--tomatoes", type=int, default=4, help="番茄数量")
    return parser.parse_args()


def main():
    args = parse_args()
    
    timer = PomodoroTimer(
        work_minutes=args.work,
        break_minutes=args.break_time,
        total_tomatoes=args.tomatoes
    )
    
    # 设置信号处理 Ctrl+C
    def signal_handler(sig, frame):
        print("\n\n👋 再见!")
        timer.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # 打印启动信息
    print(f"🍅 番茄钟开始! 工作 {args.work} 分钟, 休息 {args.break_time} 分钟")
    print(f"   共 {args.tomatoes} 个番茄")
    print("   空格键暂停/继续, Ctrl+C 退出\n")
    
    # 在主线程运行计时器
    # 使用非阻塞方式检测键盘输入
    import select
    import tty
    import termios
    
    def get_key():
        """检测是否有按键输入"""
        return select.select([sys.stdin], [], [], 0)[0]
    
    # 保存终端设置
    old_settings = termios.tcgetattr(sys.stdin)
    
    try:
        tty.setcbreak(sys.stdin.fileno())
        
        timer_thread = threading.Thread(target=timer.start)
        timer_thread.start()
        
        while timer.is_running and timer_thread.is_alive():
            if get_key():
                key = sys.stdin.read(1)
                if key == ' ':
                    timer.pause()
                    
        timer_thread.join()
        
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


if __name__ == "__main__":
    main()