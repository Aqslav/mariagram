import os
import readchar
import sys
from tonia import Color
if os.name == "nt":
    import msvcrt
else:
    import termios

STD_INPUT_HANDLE = -10

class PageWriter():
    def __init__(self, page_width = None, page_height = None, header=None, left_keys = ["a", "\x00K", "\x1b[D"], right_keys = ["d", "\x00M", "\x1b[C"], exit_keys = ["\x1b","w","\x1b\x1b"], update_keys = ["\r",'\n']):
        if page_width is None:
            page_width = os.get_terminal_size().columns
        if page_height is None:
            page_height = os.get_terminal_size().lines
        self.page_width = page_width
        self.page_height = page_height
        self.header = header
        self.text = ""
        self.current_page = 0
        self.left_keys = left_keys
        self.right_keys = right_keys
        self.exit_keys = exit_keys
        self.update_keys = update_keys
        self.wait = True

    @staticmethod
    def clear():
        os.system('cls' if os.name == 'nt' else 'clear')

    def write(self, *text, endswith="\n"):
        self.text += " ".join(text) + endswith
        if not self.wait:
            pages = PageWriter.split_pages(self.text, self.page_width, self.page_height, self.header)
            if self.current_page >= len(pages) - 1:
                self.update()

    @staticmethod
    def split_text(text, page_width):
        lines = []
        for char in str(text):
            if len(lines) == 0 or len(lines[-1]) >= page_width or char == "\n":
                lines.append("")
            if char != "\n":
                lines[-1] += char
        return lines
    
    @staticmethod
    def split_pages(text, page_width, page_height, header=None):
        lines = PageWriter.split_text(text, page_width)
        pages = []
        header_height = 0
        if header:
            header_lines = PageWriter.split_text(header, page_width)
            header_height = len(header_lines)
        for i in range(0, len(lines), page_height-header_height):
            pages.append('\n'.join(lines[i:i+page_height-header_height]))
        return pages

    def update(self):
        pages = PageWriter.split_pages(self.text, self.page_width, self.page_height, self.header)
        self.clear()
        self.current_page = max(0, min(self.current_page, len(pages) - 1))
        if len(pages) > 0:
            print(f"{self.header}\n" if self.header else "", end="")
            print(pages[self.current_page])
            print(f"\n{Color.Foreground.RESET}{Color.Background.RESET}Page {self.current_page + 1} of {len(pages)}")

    if os.name == "nt":
        @staticmethod
        def clear_console_input():
            while msvcrt.kbhit():
                msvcrt.getch()
    else:
        @staticmethod
        def clear_console_input():
            termios.tcflush(sys.stdin, termios.TCIFLUSH)

    def loop(self):
        self.wait = False
        self.update()

        while True:
            key = readchar.readkey()
            if key in self.left_keys:
                self.current_page -= 1
                self.update()
            elif key in self.right_keys:
                self.current_page += 1
                self.update()
            elif key in self.update_keys:
                self.update()
            elif key in self.exit_keys:
                break
        PageWriter.clear_console_input()

if __name__ == "__main__":
    print("Press keys to see their codes. Press Ctrl+C to exit.\n")
    while True:
        try:
            key = readchar.readkey()
            print(f"repr: {repr(key)}")
            print(f"ord : {[ord(c) for c in key]}")
            print("-" * 30)
        except KeyboardInterrupt:
            print("\nExiting...")
            break