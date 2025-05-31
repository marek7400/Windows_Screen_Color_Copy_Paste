import sys
import re
import os
import time
import traceback
import threading

# Global exception hook for better debugging in .exe
def global_exception_hook(exctype, value, tb_obj):
    """Catches all unhandled exceptions and logs them."""
    try:
        log_func = log_message
    except NameError:
        log_func = lambda msg: print(f"[CRITICAL_ERROR_LOG] {msg}", flush=True)

    log_func(f"UNHANDLED GLOBAL EXCEPTION: {exctype.__name__}")
    log_func(f"Value: {value}")
    log_func("Traceback:")
    formatted_tb = traceback.format_tb(tb_obj)
    for line in formatted_tb:
        log_func(line.strip())
    sys.exit(1)

sys.excepthook = global_exception_hook

# Definition of log_message at the very beginning
def log_message(message: str):
    """Logs a message to standard output with the [LOG] prefix."""
    print(f"[LOG] {message}", flush=True)

def get_script_or_exe_path():
    """Determines the actual path of the script or frozen executable."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # PyInstaller/Nuitka bundled app
        return os.path.dirname(sys.executable)
    try:
        # Path of the script file
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        # __file__ is not defined, e.g. in interactive interpreter or when run with exec.
        # Try sys.argv[0] as a fallback for the script path.
        try:
            return os.path.dirname(os.path.abspath(sys.argv[0]))
        except Exception:
            log_message("Warning: Could not reliably determine application script/executable path. APP_BASE_PATH will default to CWD.")
            return os.getcwd()


APP_BASE_PATH = get_script_or_exe_path() # Path of the script/executable itself
CWD_PATH = os.getcwd()                   # Current Working Directory when the script was launched

log_message(f"Application Script/Executable Path (APP_BASE_PATH) for icon loading: {APP_BASE_PATH}") # Adjusted log for clarity
log_message(f"Current Working Directory (CWD_PATH) at launch: {CWD_PATH}")


_IS_WINDOWS = os.name == 'nt'
_PSUTIL_AVAILABLE = True
try:
    import psutil
except ImportError:
    _PSUTIL_AVAILABLE = False
    log_message("psutil module is not available. Process killing functionality may not work as expected.")

_PYWIN32_AVAILABLE = True
win32gui = None 
win32con = None
win32api = None
pywintypes = None 
try:
    import pywintypes 
    import win32gui
    import win32con
    import win32api
except ImportError:
    _PYWIN32_AVAILABLE = False
    log_message("pywin32 module (win32gui, win32con, win32api, pywintypes) is not available. External dialog interaction (sending RGB values) will be disabled.")


from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QColorDialog,
    QGroupBox,
    QFormLayout,
    QGridLayout,
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QFrame,
    QMenu,
    QSpacerItem,
    QSizePolicy,
    QSystemTrayIcon,
    QStyle
)
from PySide6.QtGui import (
    QColor,
    QPalette,
    QClipboard,
    QCursor,
    QMouseEvent,
    QKeyEvent,
    QScreen,
    QCloseEvent,
    QShowEvent,
    QPixmap,
    QImage,
    QIcon,
    QAction,
)
from PySide6.QtCore import (
    Qt,
    Slot,
    Signal,
    QTimer,
    QObject,
    QRect,
    QSettings,
    QEvent,
    QPoint
)

from PIL import Image, ImageGrab, ImageDraw
from PIL.ImageQt import ImageQt

# --- Constants ---
# CONFIG_FILE_NAME = "Windows_Screen_Color_Copy_Paste.ini" # No longer used directly for path construction
STANDARD_CUSTOM_COLORS_KEY = "standardCustomColors16"
DEFAULT_SHADES_PALETTE_KEY = "defaultShadesPalette64"
USER_CUSTOM_PALETTE_KEY = "userCustomPalette64"

WIN_HUE_MAX = 239.0
WIN_SAT_LUM_MAX = 240.0
QCOLOR_HUE_MAX = 359.0
QCOLOR_SAT_LUM_VAL_MAX = 255.0

DLG_COLOR_RED_EDIT_ID = 706
DLG_COLOR_GREEN_EDIT_ID = 707
DLG_COLOR_BLUE_EDIT_ID = 708

ICON_FILE_NAME = "icon.ico" # Still used for loading the icon file


def load_application_icon(icon_filename: str) -> QIcon:
    """
    Loads an application icon from a file (expected in APP_BASE_PATH), 
    with fallbacks to standard system icons.
    """
    loaded_icon = QIcon()
    icon_path_for_log = "N/A"
    app_instance = QApplication.instance() 

    if icon_filename:
        # Use APP_BASE_PATH for icon loading (directory of script/exe)
        full_icon_path = os.path.join(APP_BASE_PATH, icon_filename)
        icon_path_for_log = full_icon_path
        if os.path.exists(full_icon_path):
            temp_icon = QIcon(full_icon_path)
            if not temp_icon.isNull():
                loaded_icon = temp_icon
                log_message(f"Icon Loader: Successfully loaded icon from APP_BASE_PATH file: {full_icon_path}")
            else:
                log_message(f"Icon Loader: APP_BASE_PATH file exists but QIcon is null (corrupt/invalid?): {full_icon_path}")
        else:
            log_message(f"Icon Loader: Icon file not found in APP_BASE_PATH: {full_icon_path}")

    if loaded_icon.isNull():
        log_message(f"Icon Loader: APP_BASE_PATH file '{icon_path_for_log}' failed or not specified. Trying QStyle.StandardPixmap.ApplicationIcon.")
        if app_instance:
            try:
                std_app_icon = app_instance.style().standardIcon(QStyle.StandardPixmap.ApplicationIcon)
                if not std_app_icon.isNull():
                    loaded_icon = std_app_icon
                    log_message("Icon Loader: Used QStyle.StandardPixmap.ApplicationIcon.")
                else:
                    log_message("Icon Loader: QStyle.StandardPixmap.ApplicationIcon is null. Trying SP_ApplicationIcon.")
                    try: 
                        std_app_icon_sp = app_instance.style().standardIcon(QStyle.SP_ApplicationIcon)
                        if not std_app_icon_sp.isNull():
                            loaded_icon = std_app_icon_sp
                            log_message("Icon Loader: Used QStyle.SP_ApplicationIcon.")
                        else:
                            log_message("Icon Loader: QStyle.SP_ApplicationIcon is also null.")
                    except AttributeError:
                        log_message("Icon Loader: QStyle.SP_ApplicationIcon not available.")
                    except Exception as e_sp:
                        log_message(f"Icon Loader: Error with QStyle.SP_ApplicationIcon: {e_sp}")
            except AttributeError: 
                log_message("Icon Loader: QStyle.StandardPixmap.ApplicationIcon not available. Trying SP_ApplicationIcon directly.")
                try: 
                    std_app_icon_sp = app_instance.style().standardIcon(QStyle.SP_ApplicationIcon)
                    if not std_app_icon_sp.isNull():
                        loaded_icon = std_app_icon_sp
                        log_message("Icon Loader: Used QStyle.SP_ApplicationIcon directly.")
                    else:
                        log_message("Icon Loader: QStyle.SP_ApplicationIcon (direct try) is also null.")
                except AttributeError:
                    log_message("Icon Loader: QStyle.SP_ApplicationIcon (direct try) not available.")
                except Exception as e_sp_direct:
                    log_message(f"Icon Loader: Error with QStyle.SP_ApplicationIcon (direct try): {e_sp_direct}")
            except Exception as e:
                log_message(f"Icon Loader: Error loading QStyle.StandardPixmap.ApplicationIcon or SP_ApplicationIcon: {e}")
        else:
            log_message("Icon Loader: QApplication instance not available for style().standardIcon.")

    if loaded_icon.isNull():
        log_message(f"Icon Loader: Fallback to ApplicationIcon failed. Trying QStyle.StandardPixmap.ComputerIcon.")
        if app_instance:
            try:
                std_comp_icon = app_instance.style().standardIcon(QStyle.StandardPixmap.ComputerIcon)
                if not std_comp_icon.isNull():
                    loaded_icon = std_comp_icon
                    log_message("Icon Loader: Used QStyle.StandardPixmap.ComputerIcon.")
                else:
                    log_message("Icon Loader: QStyle.StandardPixmap.ComputerIcon is null. Trying SP_ComputerIcon.")
                    try:
                        std_comp_icon_sp = app_instance.style().standardIcon(QStyle.SP_ComputerIcon)
                        if not std_comp_icon_sp.isNull():
                            loaded_icon = std_comp_icon_sp
                            log_message("Icon Loader: Used QStyle.SP_ComputerIcon.")
                        else:
                            log_message("Icon Loader: QStyle.SP_ComputerIcon is also null.")
                    except AttributeError:
                        log_message("Icon Loader: QStyle.SP_ComputerIcon not available.")
                    except Exception as e_sp_comp:
                         log_message(f"Icon Loader: Error with QStyle.SP_ComputerIcon: {e_sp_comp}")
            except AttributeError:
                log_message("Icon Loader: QStyle.StandardPixmap.ComputerIcon not available. Trying SP_ComputerIcon directly.")
                try:
                    std_comp_icon_sp = app_instance.style().standardIcon(QStyle.SP_ComputerIcon)
                    if not std_comp_icon_sp.isNull():
                        loaded_icon = std_comp_icon_sp
                        log_message("Icon Loader: Used QStyle.SP_ComputerIcon directly.")
                    else:
                        log_message("Icon Loader: QStyle.SP_ComputerIcon (direct try) is also null.")
                except AttributeError:
                    log_message("Icon Loader: QStyle.SP_ComputerIcon (direct try) not available.")
                except Exception as e_sp_comp_direct:
                    log_message(f"Icon Loader: Error with QStyle.SP_ComputerIcon (direct try): {e_sp_comp_direct}")
            except Exception as e:
                log_message(f"Icon Loader: Error loading QStyle.StandardPixmap.ComputerIcon or SP_ComputerIcon: {e}")
        else:
            log_message("Icon Loader: QApplication instance not available for style().standardIcon (ComputerIcon).")

    if loaded_icon.isNull():
        log_message(f"Icon Loader: All icon loading attempts (APP_BASE_PATH file '{icon_path_for_log}' & fallbacks) failed. Null QIcon.")
    return loaded_icon

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller/Nuitka. """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".") 
    return os.path.join(base_path, relative_path)


def kill_lingering_processes_by_name(process_name="WindowsScreenColorCopyPaste.exe"):
    """
    Terminates other running instances of a process with the given name.
    """
    if not _IS_WINDOWS:
        log_message(f"Killing processes by name is only supported on Windows. System: {os.name}")
        return
    if not _PSUTIL_AVAILABLE:
        log_message(f"psutil module is not available. Cannot terminate processes '{process_name}'.")
        return

    log_message(f"Attempting to terminate previous instances of process '{process_name}'...")
    killed_count = 0
    current_pid = os.getpid()

    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'].lower() == process_name.lower():
                if proc.info['pid'] == current_pid:
                    continue

                log_message(f"Found process '{proc.info['name']}' (PID: {proc.info['pid']}). Attempting to terminate...")
                p = psutil.Process(proc.info['pid'])
                p.kill()
                try:
                    p.wait(timeout=1)
                except psutil.TimeoutExpired:
                    log_message(f"Timeout expired waiting for process {proc.info['pid']} ({proc.info['name']}) to terminate.")
                killed_count += 1
                log_message(f"Terminated process {proc.info['pid']} ({proc.info['name']})")
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied:
            log_message(f"Access denied while trying to terminate process {proc.info['pid']} ({proc.info['name']}).")
        except Exception as e_kill:
            log_message(f"Error while trying to terminate process {proc.info['pid']} ({proc.info['name']}): {e_kill}")

    if killed_count > 0:
        log_message(f"Terminated {killed_count} previous instances of process '{process_name}'.")
    else:
        log_message(f"No other instances (or failed to terminate) of process '{process_name}' found to kill.")


class UpdateSignalEmitter(QObject):
    update_ready = Signal(QImage, int, int)

class MouseMagnifier(QWidget):
    def __init__(self):
        super().__init__()
        self.capture_size = 10
        self.magnifier_size = 200
        self.init_ui()
        self.running = True
        self.signal_emitter = UpdateSignalEmitter()
        self.signal_emitter.update_ready.connect(self.handle_gui_update)
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()

    def init_ui(self):
        self.setWindowTitle("Magnifier (colorPASTE)")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setGeometry(100, 100, self.magnifier_size, self.magnifier_size)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0,0,0,0)
        self.image_label = QLabel(self)
        self.image_label.setStyleSheet("background-color: black; border: 1px solid white;")
        self.image_label.setFixedSize(self.magnifier_size, self.magnifier_size)
        self.main_layout.addWidget(self.image_label)
        self.show()

    def closeEvent(self, event: QCloseEvent):
        log_message("MouseMagnifier: closeEvent called.")
        self.running = False
        if self.update_thread and self.update_thread.is_alive():
            log_message("MouseMagnifier: Waiting for update thread to finish...")
            self.update_thread.join(timeout=0.5)
            if self.update_thread.is_alive():
                log_message("MouseMagnifier: Update thread did not finish within timeout.")
            else:
                log_message("MouseMagnifier: Update thread finished.")
        event.accept()

    def close_app(self):
        log_message("MouseMagnifier: close_app called.")
        self.running = False
        self.close()

    def get_mouse_pos(self):
        pos = QCursor.pos()
        return pos.x(), pos.y()

    def capture_and_mark(self, x: int, y: int):
        try:
            scale = self.magnifier_size / self.capture_size
            half_capture_dim = self.capture_size // 2
            cap_left = x - half_capture_dim; cap_top = y - half_capture_dim
            cap_right = cap_left + self.capture_size; cap_bottom = cap_top + self.capture_size
            screenshot = ImageGrab.grab(bbox=(cap_left, cap_top, cap_right, cap_bottom), all_screens=True)
            big_image = screenshot.resize((self.magnifier_size, self.magnifier_size), Image.Resampling.NEAREST)
            draw = ImageDraw.Draw(big_image)
            block_x0 = half_capture_dim * scale; block_y0 = half_capture_dim * scale
            draw.rectangle([block_x0, block_y0, block_x0 + scale - 1, block_y0 + scale - 1], outline='red', width=1)
            center_x = block_x0 + scale / 2; center_y = block_y0 + scale / 2
            cross_arm_len = max(1, int(scale / 6))
            draw.line([center_x - cross_arm_len, center_y, center_x + cross_arm_len, center_y], fill='black', width=3)
            draw.line([center_x, center_y - cross_arm_len, center_x, center_y + cross_arm_len], fill='black', width=3)
            draw.line([center_x - cross_arm_len, center_y, center_x + cross_arm_len, center_y], fill='white', width=1)
            draw.line([center_x, center_y - cross_arm_len, center_x, center_y + cross_arm_len], fill='white', width=1)
            return big_image
        except Exception:
            return Image.new('RGB', (int(self.magnifier_size), int(self.magnifier_size)), 'black')

    def update_loop(self):
        log_message("MouseMagnifier: Update_loop thread started.")
        while self.running:
            try:
                mx, my = self.get_mouse_pos()
                pil_img = self.capture_and_mark(mx, my)
                if pil_img and self.running:
                    qimage_for_signal = ImageQt(pil_img)
                    primary_screen = QApplication.primaryScreen()
                    if not primary_screen:
                        time.sleep(0.03)
                        continue
                    sg = primary_screen.geometry()
                    sw, sh = sg.width(), sg.height()
                    offset = 20
                    wx, wy = mx + offset, my + offset
                    if wx + self.magnifier_size > sw: wx = mx - self.magnifier_size - offset
                    if wy + self.magnifier_size > sh: wy = my - self.magnifier_size - offset
                    if wx < 0: wx = 0
                    if wy < 0: wy = 0
                    self.signal_emitter.update_ready.emit(qimage_for_signal, wx, wy)
                time.sleep(0.03)
            except Exception:
                if not self.running:
                    log_message("MouseMagnifier: Update_loop thread interrupted (running=False in exception).")
                    break
                time.sleep(0.1)
        log_message("MouseMagnifier: Update_loop thread finished.")


    @Slot(QImage, int, int)
    def handle_gui_update(self, qimage: QImage, new_x: int, new_y: int):
        if not self.running or not self.isVisible():
            return
        try:
            self.image_label.setPixmap(QPixmap.fromImage(qimage))
            self.move(new_x, new_y)
        except Exception:
            pass

def _find_windows_color_dialog_hwnd():
    """
    Finds the standard Windows Color Picker dialog HWND.
    Iterates through top-level windows, checks class and child controls.
    Returns HWND or None.
    """
    if not _PYWIN32_AVAILABLE:
        log_message("Color Picker Verif: pywin32 not available.")
        return None

    dialog_class_name = "#32770"
    found_hwnd_holder = {'hwnd': None} 

    def enum_windows_proc(hwnd, lParam_holder):
        if win32gui.GetClassName(hwnd) == dialog_class_name:
            h_edit_r = win32gui.GetDlgItem(hwnd, DLG_COLOR_RED_EDIT_ID)
            h_edit_g = win32gui.GetDlgItem(hwnd, DLG_COLOR_GREEN_EDIT_ID)
            h_edit_b = win32gui.GetDlgItem(hwnd, DLG_COLOR_BLUE_EDIT_ID)
            
            if h_edit_r and h_edit_g and h_edit_b:
                log_message(f"Color Picker Verif: Found potential HWND {hwnd} (class '{dialog_class_name}') with RGB edit controls.")
                lParam_holder['hwnd'] = hwnd
                return False 
        return True 

    try:
        win32gui.EnumWindows(enum_windows_proc, found_hwnd_holder)
    except pywintypes.error as e:
        log_message(f"Color Picker Verif: pywintypes.error during/after EnumWindows: code={e.winerror}, func='{e.funcname}', msg='{e.strerror}'")
        if e.winerror == 0 and e.funcname == 'EnumWindows' and not found_hwnd_holder['hwnd']:
             log_message("Color Picker Verif: EnumWindows failed critically before finding a candidate.")
             return None
        elif not found_hwnd_holder['hwnd']: 
            log_message("Color Picker Verif: EnumWindows failed with an error before finding a candidate.")
            return None
    except Exception as e:
        log_message(f"Color Picker Verif: Unexpected error during EnumWindows: {e}")
        return None 

    if found_hwnd_holder['hwnd']:
        log_message(f"Color Picker Verif: Successfully confirmed HWND: {found_hwnd_holder['hwnd']}")
        return found_hwnd_holder['hwnd']
    else:
        log_message(f"Color Picker Verif: Standard Windows Color Dialog not found after enumeration.")
        return None

def send_rgb_values_to_external_dialog(r_val: int, g_val: int, b_val: int, parent_dialog_instance=None, is_hover_event: bool = False):
    """
    Sends RGB values to the standard Windows Color Picker dialog.
    """
    if not _PYWIN32_AVAILABLE:
        log_message("send_rgb_values: pywin32 module not available. Action skipped.")
        return False

    actual_window_title = "System Color Dialog" 
    hwnd = None 
    try:
        hwnd = _find_windows_color_dialog_hwnd()

        if not hwnd:
            log_message("send_rgb_values: Target dialog HWND not found by _find_windows_color_dialog_hwnd.")
            if not is_hover_event and parent_dialog_instance and parent_dialog_instance.isVisible():
                InfoPopupWindow("Standard Windows Color Dialog not found.", parent_dialog_instance, 3500).show()
            return False
        
        try:
            title_from_hwnd = win32gui.GetWindowText(hwnd)
            if title_from_hwnd: actual_window_title = title_from_hwnd
        except Exception as e_title:
            log_message(f"send_rgb_values: Warning - could not get window title for HWND {hwnd}: {e_title}.")

        log_message(f"send_rgb_values: Interacting with '{actual_window_title}' (HWND: {hwnd}). RGB=({r_val},{g_val},{b_val})")

        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE); time.sleep(0.03)
            if not is_hover_event and win32gui.GetForegroundWindow() != hwnd:
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 0,0,0,0, win32con.SWP_NOMOVE|win32con.SWP_NOSIZE|win32con.SWP_SHOWWINDOW)
                time.sleep(0.05)
        except Exception as e_fg:
            if not is_hover_event: log_message(f"send_rgb_values: Warning - error bringing '{actual_window_title}' to front: {e_fg}")

        targets = { DLG_COLOR_RED_EDIT_ID: str(r_val), DLG_COLOR_GREEN_EDIT_ID: str(g_val), DLG_COLOR_BLUE_EDIT_ID: str(b_val) }
        all_set_successfully = True
        for cid, val_str in targets.items():
            h_edit = win32gui.GetDlgItem(hwnd, cid)
            if h_edit and win32gui.GetClassName(h_edit).lower() == "edit":
                if not is_hover_event:
                    win32api.PostMessage(h_edit, win32con.WM_SETFOCUS, 0, 0); time.sleep(0.01)
                win32gui.SendMessage(h_edit, win32con.WM_SETTEXT, 0, val_str); time.sleep(0.01)
                wp_en_change = win32api.MAKELONG(cid, 0x0300)
                win32api.PostMessage(hwnd, win32con.WM_COMMAND, wp_en_change, h_edit); time.sleep(0.01)
            else:
                log_message(f"send_rgb_values: Error - Control ID {cid} not an Edit control in '{actual_window_title}'.")
                all_set_successfully = False
        
        if not is_hover_event and parent_dialog_instance and parent_dialog_instance.isVisible():
            msg = f"RGB values sent to '{actual_window_title}'." if all_set_successfully else f"Failed to set some RGB values in '{actual_window_title}'."
            InfoPopupWindow(msg, parent_dialog_instance, 2500 if all_set_successfully else 4500).show()
        
        return all_set_successfully

    except pywintypes.error as e_pywin:
        log_message(f"send_rgb_values: pywintypes.error for '{actual_window_title}' (HWND: {hwnd if hwnd else 'N/A'}): {e_pywin.winerror}, '{e_pywin.funcname}', '{e_pywin.strerror}'")
        if not is_hover_event and parent_dialog_instance and parent_dialog_instance.isVisible():
             InfoPopupWindow("Error communicating with Color Dialog (pywin32 error).", parent_dialog_instance, 4000).show()
        return False
    except Exception as e_general:
        log_message(f"send_rgb_values: CRITICAL UNEXPECTED ERROR for '{actual_window_title}' (HWND: {hwnd if hwnd else 'N/A'}): {e_general}\n{traceback.format_exc()}")
        if not is_hover_event and parent_dialog_instance and parent_dialog_instance.isVisible():
             InfoPopupWindow("Unexpected error with Color Dialog.", parent_dialog_instance, 4000).show()
        return False

class ScreenColorPicker(QWidget):
    colorSelected=Signal(QColor); colorHovered=Signal(QColor); pickerClosed=Signal()
    def __init__(self,p=None):
        super().__init__(p)
        self.setWindowFlags(Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground);self.setAttribute(Qt.WA_NoSystemBackground)
        self.setCursor(Qt.CrossCursor);self._active=False;self.setMouseTracking(True)
        self.magnifier_window=None;self.show_magnifier_timer=QTimer(self)
        self.show_magnifier_timer.setSingleShot(True);self.show_magnifier_timer.timeout.connect(self._activate_picker_and_magnifier)
    def pick_color_on_screen(self):
        if not QApplication.instance():self.close();return
        if self.parent() and isinstance(self.parentWidget(),QWidget):
            self.parentWidget().setVisible(False);QApplication.processEvents()
        self._active=True;self.show_magnifier_timer.start(100)
    @Slot()
    def _activate_picker_and_magnifier(self):
        if not self._active:return
        log_message("ScreenColorPicker: Activating picker and magnifier.")
        self.showFullScreen();self.raise_();self.activateWindow()
        if not self.hasFocus():self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        QTimer.singleShot(10,self._check_focus_and_grab)
        if self.magnifier_window is None:
            log_message("ScreenColorPicker: Creating new MouseMagnifier window.")
            self.magnifier_window=MouseMagnifier()
        else:
            if not self.magnifier_window.isVisible():
                log_message("ScreenColorPicker: Showing existing MouseMagnifier window.")
                self.magnifier_window.show()
            self.magnifier_window.raise_()
    def _check_focus_and_grab(self):
        if not self._active or not self.isVisible():
            if self.isVisible():self.close()
            return
        if not self.hasFocus():
            self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        if not self.hasFocus():
            log_message("ScreenColorPicker: Still no focus after retry, closing picker.")
            self.close();return
        self.grabMouse();self.grabKeyboard()
        if not(self.mouseGrabber()==self and self.keyboardGrabber()==self):
            log_message("ScreenColorPicker: Failed to grab mouse/keyboard, closing.")
            self.close()
    def mouseMoveEvent(self,e:QMouseEvent):
        if not self._active or not self.isVisible():super().mouseMoveEvent(e);return
        gp=e.globalPosition().toPoint();s=QApplication.screenAt(gp) or QApplication.primaryScreen()
        if s:
            pxm=s.grabWindow(0,gp.x(),gp.y(),1,1)
            if not pxm.isNull():
                img=pxm.toImage()
                if not img.isNull() and img.valid(0,0):
                    c=img.pixelColor(0,0)
                    if c.isValid():self.colorHovered.emit(c)
        super().mouseMoveEvent(e)
    def mousePressEvent(self,e:QMouseEvent):
        if not self._active or self.mouseGrabber()!=self:super().mousePressEvent(e);return
        if e.button()==Qt.MouseButton.LeftButton:
            gp=e.globalPosition().toPoint();s=QApplication.screenAt(gp) or QApplication.primaryScreen()
            if s:
                pxm=s.grabWindow(0,gp.x(),gp.y(),1,1)
                if not pxm.isNull():
                    img=pxm.toImage()
                    if not img.isNull() and img.valid(0,0):
                        c=img.pixelColor(0,0)
                        if c.isValid():self.colorSelected.emit(c)
    def keyPressEvent(self,e:QKeyEvent):
        if not self._active or self.keyboardGrabber()!=self:super().keyPressEvent(e);return
        if e.key()==Qt.Key.Key_Escape:
            log_message("ScreenColorPicker: Escape pressed, closing picker.")
            self.close()
        else:super().keyPressEvent(e)
    def showEvent(self,e:QShowEvent):super().showEvent(e)
    def closeEvent(self,e:QCloseEvent):
        log_message("ScreenColorPicker: closeEvent.")
        if self.show_magnifier_timer.isActive():self.show_magnifier_timer.stop()
        if self.magnifier_window:
            log_message("ScreenColorPicker: Closing magnifier window.")
            self.magnifier_window.close_app();self.magnifier_window=None
        if self.mouseGrabber()==self:self.releaseMouse()
        if self.keyboardGrabber()==self:self.releaseKeyboard()
        self._active=False;self.pickerClosed.emit();super().closeEvent(e)
        log_message("ScreenColorPicker: Finished closeEvent.")


class InfoPopupWindow(QWidget):
    def __init__(self,m,p=None,d=2000):
        super().__init__(p)
        self.setWindowFlags(Qt.ToolTip|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.BypassWindowManagerHint)
        self.setAttribute(Qt.WA_TranslucentBackground);self.setAttribute(Qt.WA_DeleteOnClose)
        lyt=QVBoxLayout(self);lyt.setContentsMargins(10,8,10,8)
        self.lbl=QLabel(m);self.lbl.setAlignment(Qt.AlignCenter)
        self.lbl.setStyleSheet("QLabel{background-color:rgba(30,30,30,220);color:white;padding:10px 15px;border-radius:6px;font-size:14pt;max-width:450px;}")
        self.lbl.setWordWrap(True);self.lbl.setMinimumWidth(150);lyt.addWidget(self.lbl);self.adjustSize()
        if p and p.isVisible():
            pg,sg=p.geometry(),self.frameGeometry();tx=pg.x()+(pg.width()-sg.width())/2;ty=pg.y()+(pg.height()-sg.height())/2
            scr=p.screen() or QApplication.primaryScreen();scr_g=scr.availableGeometry()
            fx=max(scr_g.x(),min(tx,scr_g.x()+scr_g.width()-sg.width()));fy=max(scr_g.y(),min(ty,scr_g.y()+scr_g.height()-sg.height()))
            self.move(int(fx),int(fy))
        else:
            scr=QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen();scr_g=scr.availableGeometry()
            self.move(scr_g.center()-self.rect().center())
        QTimer.singleShot(d,self.close)

class CustomColorPaletteWidget(QWidget):
    paletteColorClicked = Signal(QColor)
    requestSaveColorToCell = Signal(int)
    cellSelectedSignal = Signal(int, QWidget)

    NUM_ROWS = 8
    NUM_COLS = 8
    TOTAL_CELLS = NUM_ROWS * NUM_COLS

    def __init__(self, populate_defaults=True, parent=None):
        super().__init__(parent)
        self.empty_color = QColor("#F0F0F0")
        self.palette_colors = [QColor(self.empty_color) for _ in range(self.TOTAL_CELLS)]
        self.color_cells_labels = []
        self.selected_cell_index = -1
        self._populate_defaults = populate_defaults
        self._init_ui()
        if self._populate_defaults:
            self.populate_default_colors()
        else:
            self.update_cells_appearance()

    def _init_ui(self):
        main_layout = QGridLayout(self)
        main_layout.setSpacing(1); main_layout.setContentsMargins(1,1,1,1)
        for i in range(self.TOTAL_CELLS):
            r, c = i // self.NUM_COLS, i % self.NUM_COLS
            lbl = QLabel()
            lbl.setFixedSize(22,22)
            lbl.setFrameShape(QFrame.Shape.Box)
            lbl.setLineWidth(1)
            lbl.setProperty("cell_index", i); lbl.installEventFilter(self)
            main_layout.addWidget(lbl,r,c); self.color_cells_labels.append(lbl)
        self.update_cells_appearance()

    def eventFilter(self, obj, event):
        if obj in self.color_cells_labels:
            idx = obj.property("cell_index")
            if event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._on_cell_clicked(idx)
                    if not self._populate_defaults: self.set_selected_cell(idx)
                    return True
                elif event.button() == Qt.MouseButton.RightButton:
                    self._show_cell_context_menu(obj, event.globalPosition().toPoint())
                    return True
        return super().eventFilter(obj, event)

    def set_selected_cell(self, index: int):
        if self.selected_cell_index != index:
            old_idx = self.selected_cell_index
            self.selected_cell_index = index
            if 0 <= old_idx < self.TOTAL_CELLS: self.update_cell_appearance(old_idx)
            if 0 <= self.selected_cell_index < self.TOTAL_CELLS: self.update_cell_appearance(self.selected_cell_index)
            self.cellSelectedSignal.emit(self.selected_cell_index, self)

    def _show_cell_context_menu(self, lbl_widget: QLabel, g_pos: QPoint):
        idx = lbl_widget.property("cell_index"); menu = QMenu(self)
        act = menu.addAction("Save current color here")
        act.triggered.connect(lambda chk=False, i=idx: self.requestSaveColorToCell.emit(i))
        menu.exec(g_pos)

    def populate_default_colors(self):
        if not self._populate_defaults: return
        hues = [0,30,60,120,180,240,300,-1]; sats = [255]*7+[0]; vals = [255,225,200,175,150,125,100,70]
        for c_idx in range(self.NUM_COLS):
            h,s = hues[c_idx], sats[c_idx]
            for r_idx in range(self.NUM_ROWS):
                v = vals[r_idx]; cell_idx = r_idx*self.NUM_COLS+c_idx
                if 0<=cell_idx<self.TOTAL_CELLS: self.palette_colors[cell_idx]=QColor.fromHsv(h,s,v)
        self.update_cells_appearance()

    def update_cells_appearance(self):
        for i in range(self.TOTAL_CELLS): self.update_cell_appearance(i)

    def _on_cell_clicked(self, cell_idx: int):
        if 0<=cell_idx<len(self.palette_colors): self.paletteColorClicked.emit(self.palette_colors[cell_idx])

    def set_color_at_index(self, idx: int, color: QColor):
        if 0<=idx<self.TOTAL_CELLS and color.isValid():
            self.palette_colors[idx]=QColor(color); self.update_cell_appearance(idx); return True
        return False

    def update_cell_appearance(self, idx: int):
        if not (0<=idx<len(self.color_cells_labels) and idx<len(self.palette_colors)): return
        color_obj = self.palette_colors[idx]
        label_widget = self.color_cells_labels[idx]
        base_style = f"background-color: {color_obj.name()}; border: 1px solid #555555;"
        if not self._populate_defaults and idx == self.selected_cell_index:
            base_style = f"background-color: {color_obj.name()}; border: 2px solid #0078D7;"
        label_widget.setStyleSheet(base_style)
        label_widget.setToolTip(f"{color_obj.name(QColor.NameFormat.HexArgb)}\nRGB: {color_obj.red()},{color_obj.green()},{color_obj.blue()}")

    def load_colors_from_settings(self, settings: QSettings, key: str):
        saved_list = settings.value(key, [])
        if isinstance(saved_list, str): saved_list = [saved_list]
        loaded_any_valid_color = False
        self.palette_colors = [QColor(self.empty_color) for _ in range(self.TOTAL_CELLS)]
        for i in range(min(len(saved_list), self.TOTAL_CELLS)):
            color_str = saved_list[i]
            if isinstance(color_str, str):
                color = QColor(color_str)
                if color.isValid():
                    self.palette_colors[i] = color
                    loaded_any_valid_color = True
        if not loaded_any_valid_color and self._populate_defaults:
            self.populate_default_colors()
            return
        self.update_cells_appearance()

    def save_colors_to_settings(self, settings: QSettings, key: str):
        to_save = [c.name(QColor.NameFormat.HexArgb) for c in self.palette_colors]
        settings.setValue(key, to_save); settings.sync()

class CustomColorPickerDialog(QDialog):
    def __init__(self, initial_color=QColor(0,120,215,255), parent=None, app_icon: QIcon = None): # Added app_icon parameter
        super().__init__(parent)
        self.setWindowTitle("Windows Screen Color Copy Paste")

        # Use the provided app_icon, with a fallback to loading it if not provided or null
        if app_icon and not app_icon.isNull():
            self.app_icon_object = app_icon
            log_message("CustomColorPickerDialog: Using application icon provided via constructor.")
        else:
            log_message("CustomColorPickerDialog: Application icon (app_icon arg) not provided or was null. Attempting to load icon independently as a fallback.")
            self.app_icon_object = load_application_icon(ICON_FILE_NAME) 

        if not self.app_icon_object.isNull():
            self.setWindowIcon(self.app_icon_object)
            log_message("CustomColorPickerDialog: Dialog window icon has been set using the resolved app_icon_object.")
        else:
            log_message("CustomColorPickerDialog: Dialog window icon remains default (resolved app_icon_object is null).")


        self.setWindowFlags(self.windowFlags()|Qt.WindowStaysOnTopHint|Qt.WindowMinMaxButtonsHint)
        self._saved_session=False
        self.sel_color=QColor(initial_color)
        self.clip=QApplication.clipboard()
        self._picker_inst=None
        self._send_tmr=QTimer(self)
        self._send_tmr.setSingleShot(True)
        self._send_tmr.timeout.connect(self._perform_send_to_external_dialog)
        self._color_to_send_tmr=None
        self.close_picker_tmr=QTimer(self)
        self.close_picker_tmr.setSingleShot(True)
        self.close_picker_tmr.timeout.connect(self._delayed_close_picker_operations)
        self.active_user_palette_sel_cell = -1
        self.tray_icon = None 

        # Configuration file management using QSettings standard locations
        ORGANIZATION_NAME = "ColorPasteOrg" # CHANGED: Example Organization Name
        APPLICATION_NAME = "WindowsScreenColorCopyPaste"

        self.settings = QSettings(QSettings.Format.IniFormat, 
                                  QSettings.Scope.UserScope, 
                                  ORGANIZATION_NAME, 
                                  APPLICATION_NAME, 
                                  self)
        
        log_message(f"Configuration file path being used by QSettings: {self.settings.fileName()}")


        overall_layout = QVBoxLayout(self)
        top_panel_w = QWidget(); top_panel_h_lyt = QHBoxLayout(top_panel_w)
        left_panel_w = QWidget(); left_lyt = QVBoxLayout(left_panel_w)
        self.c_dialog_w = QColorDialog(self.sel_color,self)
        self.c_dialog_w.setOption(QColorDialog.ColorDialogOption.NoButtons)
        self.c_dialog_w.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel)
        self.c_dialog_w.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog,True)
        self.c_dialog_w.currentColorChanged.connect(self.on_color_dialog_widget_changed)
        left_lyt.addWidget(self.c_dialog_w); top_panel_h_lyt.addWidget(left_panel_w,2)

        right_panel_w = QWidget(); right_lyt = QVBoxLayout(right_panel_w)
        vals_grp = QGroupBox("Color Values"); vals_form_lyt = QFormLayout(vals_grp)
        vals_form_lyt.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_rgb=QLabel();self.lbl_rgba=QLabel();self.lbl_hex_rgb=QLabel();self.lbl_hex_argb=QLabel()
        self.lbl_hsv=QLabel();self.lbl_dec=QLabel();self.lbl_hsl_win=QLabel();self.lbl_cmyk=QLabel()
        vals_form_lyt.addRow("RGB:",self.lbl_rgb);vals_form_lyt.addRow("RGBA:",self.lbl_rgba)
        vals_form_lyt.addRow("HTML:",self.lbl_hex_rgb);vals_form_lyt.addRow("HEX ARGB:",self.lbl_hex_argb)
        vals_form_lyt.addRow("HSL(Win):",self.lbl_hsl_win);vals_form_lyt.addRow("HSV:",self.lbl_hsv)
        vals_form_lyt.addRow("CMYK:",self.lbl_cmyk);vals_form_lyt.addRow("Decimal:",self.lbl_dec)
        right_lyt.addWidget(vals_grp)

        cpy_grp=QGroupBox("COPY TO CLIPBOARD");cpy_lyt=QGridLayout(cpy_grp)
        self.cp_rgb=QPushButton("RGB");self.cp_rgba=QPushButton("RGBA");self.cp_html=QPushButton("HTML")
        self.cp_hsv=QPushButton("HSV");self.cp_hsl=QPushButton("HSL");self.cp_cmyk=QPushButton("CMYK")
        self.cp_hex_argb=QPushButton("#ARGB");self.cp_dec=QPushButton("Dec");self.cp_all=QPushButton("ALL")
        cpy_lyt.addWidget(self.cp_rgb,0,0);cpy_lyt.addWidget(self.cp_rgba,0,1);cpy_lyt.addWidget(self.cp_html,1,0)
        cpy_lyt.addWidget(self.cp_hsv,1,1);cpy_lyt.addWidget(self.cp_hsl,2,0);cpy_lyt.addWidget(self.cp_cmyk,2,1)
        cpy_lyt.addWidget(self.cp_hex_argb,3,0);cpy_lyt.addWidget(self.cp_dec,3,1);cpy_lyt.addWidget(self.cp_all,4,0,1,2)
        self.cp_rgb.clicked.connect(lambda:self.copy_to_clipboard(self._format_rgb(),"RGB")); self.cp_rgba.clicked.connect(lambda:self.copy_to_clipboard(self._format_rgba(),"RGBA"))
        self.cp_html.clicked.connect(lambda:self.copy_to_clipboard(self._format_html(),"HTML"));self.cp_hsv.clicked.connect(lambda:self.copy_to_clipboard(self._format_hsv_for_copy(),"HSV"))
        self.cp_hsl.clicked.connect(lambda:self.copy_to_clipboard(self._format_hsl_for_copy(),"HSL"));self.cp_cmyk.clicked.connect(lambda:self.copy_to_clipboard(self._format_cmyk_for_copy(),"CMYK"))
        self.cp_hex_argb.clicked.connect(lambda:self.copy_to_clipboard(self._format_hex_argb(),"#ARGB"));self.cp_dec.clicked.connect(lambda:self.copy_to_clipboard(self._format_decimal_qrgb(),"Dec"))
        self.cp_all.clicked.connect(self.copy_all_values_to_clipboard);right_lyt.addWidget(cpy_grp)

        act_grp=QGroupBox("Actions");act_lyt=QVBoxLayout(act_grp)
        self.pick_btn=QPushButton("Pick Color from Screen"); self.pick_btn.setToolTip("Pick a color from anywhere on the screen")
        self.pick_btn.clicked.connect(self.start_screen_color_pick);act_lyt.addWidget(self.pick_btn);right_lyt.addWidget(act_grp)
        right_lyt.addStretch();top_panel_h_lyt.addWidget(right_panel_w,1);overall_layout.addWidget(top_panel_w)

        palettes_cont_w = QWidget(); palettes_h_lyt = QHBoxLayout(palettes_cont_w)
        palettes_h_lyt.setContentsMargins(0,0,0,0)
        def_pal_grp = QGroupBox("Default Shades"); def_pal_lyt = QVBoxLayout(def_pal_grp)
        self.def_shades_pal_w = CustomColorPaletteWidget(True,self)
        self.def_shades_pal_w.paletteColorClicked.connect(self.handle_palette_color_cell_clicked)
        self.def_shades_pal_w.requestSaveColorToCell.connect(lambda idx, pal=self.def_shades_pal_w, key=DEFAULT_SHADES_PALETTE_KEY: self.handle_request_save_to_specific_palette(idx,pal,key))
        def_pal_lyt.addWidget(self.def_shades_pal_w); palettes_h_lyt.addWidget(def_pal_grp)
        palettes_h_lyt.addSpacerItem(QSpacerItem(20,10,QSizePolicy.Policy.Fixed,QSizePolicy.Policy.Minimum))

        usr_pal_outer_grp = QGroupBox("User Palette"); usr_pal_outer_lyt = QVBoxLayout(usr_pal_outer_grp)
        self.add_to_usr_pal_btn = QPushButton("Add color to selected spot")
        self.add_to_usr_pal_btn.clicked.connect(self.handle_add_color_to_user_palette)
        usr_pal_outer_lyt.addWidget(self.add_to_usr_pal_btn)
        self.usr_cust_pal_w = CustomColorPaletteWidget(False,self)
        self.usr_cust_pal_w.paletteColorClicked.connect(self.handle_palette_color_cell_clicked)
        self.usr_cust_pal_w.cellSelectedSignal.connect(self.handle_user_palette_cell_selection)
        self.usr_cust_pal_w.requestSaveColorToCell.connect(lambda idx, pal=self.usr_cust_pal_w, key=USER_CUSTOM_PALETTE_KEY: self.handle_request_save_to_specific_palette(idx,pal,key))
        usr_pal_outer_lyt.addWidget(self.usr_cust_pal_w); palettes_h_lyt.addWidget(usr_pal_outer_grp)
        overall_layout.addWidget(palettes_cont_w)

        self.btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        self.btn_box.button(QDialogButtonBox.StandardButton.Ok).setText("OK")
        self.btn_box.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancel")
        self.btn_box.accepted.connect(self.handle_accepted_signal); self.btn_box.rejected.connect(self.handle_rejected_signal)
        overall_layout.addWidget(self.btn_box); self.setLayout(overall_layout)

        self._load_custom_colors()
        self.def_shades_pal_w.load_colors_from_settings(self.settings,DEFAULT_SHADES_PALETTE_KEY)
        self.usr_cust_pal_w.load_colors_from_settings(self.settings,USER_CUSTOM_PALETTE_KEY)
        self.update_all_displays(); self._hide_standard_eyedropper_button()
        self._setup_tray_icon()

    def _setup_tray_icon(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            log_message("System tray is not available.")
            return

        icon_to_use_for_tray = self.app_icon_object 
                                     
        if icon_to_use_for_tray.isNull():
             log_message("Tray Icon: self.app_icon_object (the resolved application icon) is null. Tray icon may be invisible or system default.")
        
        self.tray_icon = QSystemTrayIcon(icon_to_use_for_tray, self)

        if self.tray_icon.icon().isNull(): # Check if QSystemTrayIcon successfully adopted the icon
            log_message("Tray Icon: QSystemTrayIcon reports its icon is null (even if a non-null QIcon was provided - system limitation or icon format issue?).")
        else:
            log_message("Tray Icon: QSystemTrayIcon successfully set with a valid icon (same as application/dialog icon).")


        self.tray_icon.setToolTip(f"{self.windowTitle()}\nClick to show/hide.")
        tray_menu = QMenu(self)
        show_action = QAction("Show", self); show_action.triggered.connect(self.bring_to_front)
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        quit_action = QAction("Quit", self); quit_action.triggered.connect(self._quit_application_from_tray)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._tray_icon_activated)
        self.tray_icon.show()
        log_message("Tray icon configured and shown (or attempted).")

    @Slot(QSystemTrayIcon.ActivationReason)
    def _tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger: 
            if self.isVisible():
                self.bring_to_front() 
            else:
                self.bring_to_front()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
             self.bring_to_front()

    def bring_to_front(self):
        self.showNormal()
        self.activateWindow() 
        self.raise_()         

    def _quit_application_from_tray(self):
        log_message("Quit action from tray menu: triggering main window close.")
        self.close() 

    def _save_all_settings(self):
        log_message("Saving all settings (QColorDialog custom colors, default palette, user palette).")
        self._save_custom_colors()
        self.def_shades_pal_w.save_colors_to_settings(self.settings, DEFAULT_SHADES_PALETTE_KEY)
        self.usr_cust_pal_w.save_colors_to_settings(self.settings, USER_CUSTOM_PALETTE_KEY)
        self.settings.sync() # Ensure data is written to disk
        log_message(f"Settings saving finished. Synced to: {self.settings.fileName()}")

    @Slot()
    def handle_user_palette_cell_selection(self,cell_idx:int,pal_w_inst:QWidget):
        if pal_w_inst == self.usr_cust_pal_w:
            self.active_user_palette_sel_cell = cell_idx
            if self.def_shades_pal_w.selected_cell_index != -1:
                 self.def_shades_pal_w.set_selected_cell(-1)
            if self.usr_cust_pal_w.selected_cell_index != cell_idx :
                self.usr_cust_pal_w.set_selected_cell(cell_idx)

    @Slot()
    def handle_add_color_to_user_palette(self):
        if self.active_user_palette_sel_cell != -1:
            if self.sel_color and self.sel_color.isValid():
                if self.usr_cust_pal_w.set_color_at_index(self.active_user_palette_sel_cell, self.sel_color):
                    InfoPopupWindow(f"Color saved to user palette.", self, 2000).show()
            else: InfoPopupWindow("No valid color selected.", self, 2500).show()
        else: InfoPopupWindow("No spot selected in user palette.", self, 3000).show()

    @Slot(int, QWidget, str)
    def handle_request_save_to_specific_palette(self,cell_idx:int,pal_w:CustomColorPaletteWidget,s_key:str):
        if self.sel_color and self.sel_color.isValid():
            if pal_w.set_color_at_index(cell_idx, self.sel_color):
                palette_name = "default" if pal_w == self.def_shades_pal_w else "user"
                InfoPopupWindow(f"Color saved in {palette_name} palette.", self, 2000).show()
        else: InfoPopupWindow("No valid color selected to save.", self, 2500).show()

    @Slot()
    def handle_accepted_signal(self):
        log_message("Accepted signal (OK) received."); self.accept()
    @Slot()
    def handle_rejected_signal(self):
        log_message("Rejected signal (Cancel) received."); self.reject()

    def accept(self):
        log_message("accept() method called.")
        self._save_all_settings()
        self._saved_session = True 
        super().accept() 

    def reject(self):
        log_message("reject() method called.")
        self._save_all_settings() # Save settings even on cancel/close via 'X'
        self._saved_session = True 
        super().reject() 

    def _load_custom_colors(self):
        # No need to check for file existence here, QSettings handles it.
        # If the file doesn't exist, settings.value() will return the default.
        s_colors = self.settings.value(STANDARD_CUSTOM_COLORS_KEY,[])
        if isinstance(s_colors,str): s_colors=[s_colors]
        default_color = QColor(Qt.GlobalColor.white)
        log_message(f"Loading QColorDialog custom colors from '{self.settings.fileName()}' ({len(s_colors)} items found).")
        
        loaded_count = 0
        for i in range(16):
            c_set = default_color
            if i<len(s_colors) and isinstance(s_colors[i],str):
                try:
                    temp_color=QColor(s_colors[i])
                    if temp_color.isValid(): 
                        c_set=temp_color
                        loaded_count +=1
                except Exception as e:
                    log_message(f"Error parsing QColorDialog custom color '{s_colors[i]}': {e}. Used default.")
            self.c_dialog_w.setCustomColor(i,c_set.rgb())
        if not s_colors or loaded_count == 0:
             log_message(f"No QColorDialog custom colors found or loaded from settings file. Using defaults.")


    def _save_custom_colors(self):
        try:
            log_message(f"Saving QColorDialog custom colors to '{self.settings.fileName()}'.")
            custom_colors = []
            for i in range(16): 
                color_instance = self.c_dialog_w.customColor(i)
                # QColorDialog.customColor(idx) returns an int (QRgb). We need to convert it back to QColor.
                # However, it seems QColorDialog stores them internally and can give them back
                # If it gives an int, we convert. If it gives QColor, we use it.
                # For safety, always create QColor from the retrieved value if it's not already one.
                if isinstance(color_instance, int): # It's a QRgb value
                    color_instance = QColor.fromRgb(color_instance)

                if not (isinstance(color_instance, QColor) and color_instance.isValid()):
                    log_message(f"Invalid custom color retrieved/converted from QColorDialog at position {i}, using white as fallback for saving.")
                    color_instance = QColor(Qt.GlobalColor.white) 
                
                custom_colors.append(color_instance.name(QColor.NameFormat.HexArgb))
            
            self.settings.setValue(STANDARD_CUSTOM_COLORS_KEY, custom_colors)
        except Exception as e:
            log_message(f"ERROR during saving QColorDialog custom colors: {e}\n{traceback.format_exc()}")

    def closeEvent(self, e: QCloseEvent):
        log_message("CustomColorPickerDialog: closeEvent triggered, performing full application quit.")

        if not self._saved_session:
            log_message("CustomColorPickerDialog: closeEvent - saving settings as session wasn't marked saved (e.g. closed via 'X').")
            self._save_all_settings()
            self._saved_session = True

        if self._picker_inst and self._picker_inst.isVisible():
            log_message("CustomColorPickerDialog: closeEvent - closing ScreenColorPicker instance.")
            self._picker_inst.close()
            QApplication.processEvents()

        if self.tray_icon and self.tray_icon.isVisible():
            log_message("CustomColorPickerDialog: closeEvent - hiding tray icon before application quit.")
            self.tray_icon.hide()

        log_message("CustomColorPickerDialog: closeEvent - accepting window close and signaling application quit.")
        e.accept()
        QApplication.instance().quit()

    def _hide_standard_eyedropper_button(self):
        try:
            btn = self.c_dialog_w.findChild(QPushButton, "qt_colordetail_eyedropper")
            if btn: btn.hide(); log_message("Hid standard QColorDialog eyedropper button."); return True
            else: log_message("Standard QColorDialog eyedropper button ('qt_colordetail_eyedropper') not found.")
        except Exception as e: log_message(f"Error while hiding standard eyedropper: {e}")
        return False

    @Slot()
    def start_screen_color_pick(self):
        log_message("Starting screen color pick.")
        if self._picker_inst and self._picker_inst.isVisible():
            log_message("Closing previous ScreenColorPicker instance.")
            self._picker_inst.close();QApplication.processEvents()
        self._picker_inst=ScreenColorPicker(self)
        self._picker_inst.colorSelected.connect(self.on_screen_color_picked)
        self._picker_inst.colorHovered.connect(self.handle_color_hovered_from_picker)
        self._picker_inst.pickerClosed.connect(self.restore_dialog_after_picker_closed)
        self._picker_inst.pick_color_on_screen()

    @Slot(QColor)
    def handle_color_hovered_from_picker(self,c:QColor):
        if c.isValid(): self._color_to_send_tmr=c
        if not self._send_tmr.isActive(): self._send_tmr.start(50) 

    @Slot()
    def _perform_send_to_external_dialog(self):
        if self._color_to_send_tmr and self._color_to_send_tmr.isValid():
            send_rgb_values_to_external_dialog(
                self._color_to_send_tmr.red(),
                self._color_to_send_tmr.green(),
                self._color_to_send_tmr.blue(),
                self, 
                True  
            )
            self._color_to_send_tmr=None

    @Slot(QColor)
    def on_screen_color_picked(self,c:QColor):
        log_message(f"Picked color from screen: {c.name()}")
        if c.isValid():
            if self._send_tmr.isActive():self._send_tmr.stop()
            self._color_to_send_tmr=None;self.c_dialog_w.setCurrentColor(c)
            log_message(f"Sending picked color {c.name()} to external dialog.")
            
            found_ext=send_rgb_values_to_external_dialog(c.red(),c.green(),c.blue(),self, False) 
            rgb_txt=f"{c.red()},{c.green()},{c.blue()}"
            if self.clip: self.clip.setText(rgb_txt); log_message(f"Copied RGB ({rgb_txt}) to clipboard.")
            else: log_message("Error: Clipboard not accessible.")
            
            pop_parts=[f"Copied RGB:\n{rgb_txt}"]
            if found_ext:
                pop_parts.append("Sent to system color dialog.")

            parent_for_popup = self if self.isVisible() else None
            InfoPopupWindow("\n".join(pop_parts),parent_for_popup,3000).show()
            self.close_picker_tmr.start(100)

    @Slot()
    def _delayed_close_picker_operations(self):
        log_message("Delayed closing of ScreenColorPicker.")
        if self._picker_inst:self._picker_inst.close()

    @Slot()
    def restore_dialog_after_picker_closed(self):
        log_message("Restoring main dialog after picker closed.")
        if self.close_picker_tmr.isActive():self.close_picker_tmr.stop()
        if self._send_tmr.isActive():self._send_tmr.stop()
        self._color_to_send_tmr=None
        if self._picker_inst:
            try:self._picker_inst.colorSelected.disconnect(self.on_screen_color_picked)
            except RuntimeError:pass
            try:self._picker_inst.colorHovered.disconnect(self.handle_color_hovered_from_picker)
            except RuntimeError:pass
            try:self._picker_inst.pickerClosed.disconnect(self.restore_dialog_after_picker_closed)
            except RuntimeError:pass
            self._picker_inst.deleteLater();self._picker_inst=None
        if not self.isVisible():
            log_message("Main window was not visible, showing and activating.")
            self.setVisible(True);self.raise_();self.activateWindow()
        else: log_message("Main window was already visible.")

    @Slot(QColor)
    def on_color_dialog_widget_changed(self,c:QColor):
        if self.sel_color!=c and c.isValid():
            self.sel_color=QColor(c);self.update_all_displays()
            self._color_to_send_tmr=QColor(c)
            if not self._send_tmr.isActive(): self._send_tmr.start(75) 


    def _update_hsl_inputs(self):self.lbl_hsl_win.setText(self._format_hsl_for_display())
    def _update_cmyk_inputs(self):self.lbl_cmyk.setText(self._format_cmyk_for_display())
    def update_all_displays(self):
        self.lbl_rgb.setText(self._format_rgb());self.lbl_rgba.setText(self._format_rgba())
        self.lbl_hex_rgb.setText(self._format_html());self.lbl_hex_argb.setText(self._format_hex_argb())
        self._update_hsl_inputs();self.lbl_hsv.setText(self._format_hsv_for_display())
        self._update_cmyk_inputs();self.lbl_dec.setText(self._format_decimal_qrgb())

    def _format_rgb(self)->str:return f"{self.sel_color.red()},{self.sel_color.green()},{self.sel_color.blue()}"
    def _format_rgba(self)->str:return f"{self.sel_color.red()},{self.sel_color.green()},{self.sel_color.blue()},{self.sel_color.alpha()}"
    def _format_html(self)->str:return self.sel_color.name(QColor.NameFormat.HexRgb)
    def _format_hsl_for_display(self)->str:
        h,s,l=self.sel_color.hue(),self.sel_color.saturation(),self.sel_color.lightness()
        wh=(h/QCOLOR_HUE_MAX)*WIN_HUE_MAX if h!=-1 else 0.0;ws=(s/QCOLOR_SAT_LUM_VAL_MAX)*WIN_SAT_LUM_MAX;wl=(l/QCOLOR_SAT_LUM_VAL_MAX)*WIN_SAT_LUM_MAX
        return f"H:{int(round(wh))} S:{int(round(ws))} L:{int(round(wl))}"
    def _format_hsl_for_copy(self)->str:
        h,s,l=self.sel_color.hue(),self.sel_color.saturation(),self.sel_color.lightness()
        wh=(h/QCOLOR_HUE_MAX)*WIN_HUE_MAX if h!=-1 else 0.0;ws=(s/QCOLOR_SAT_LUM_VAL_MAX)*WIN_SAT_LUM_MAX;wl=(l/QCOLOR_SAT_LUM_VAL_MAX)*WIN_SAT_LUM_MAX
        return f"{int(round(wh))},{int(round(ws))},{int(round(wl))}"
    def _format_hsv_for_display(self)->str:h,s,v,_=self.sel_color.getHsv();hs=str(h)if h!=-1 else"0";return f"H:{hs} S:{s} V:{v}"
    def _format_hsv_for_copy(self)->str:h,s,v,_=self.sel_color.getHsv();hs=str(h)if h!=-1 else"0";return f"{hs},{s},{v}"
    def _format_cmyk_for_display(self)->str:c,m,y,k,_=self.sel_color.getCmyk();return f"C:{c} M:{m} Y:{y} K:{k}"
    def _format_cmyk_for_copy(self)->str:c,m,y,k,_=self.sel_color.getCmyk();return f"{c},{m},{y},{k}"
    def _format_hex_argb(self)->str:return self.sel_color.name(QColor.NameFormat.HexArgb)
    def _format_decimal_qrgb(self)->str:return str(self.sel_color.rgba())

    @Slot()
    def copy_to_clipboard(self,txt:str,desc:str=""):
        if self.clip:
            self.clip.setText(txt);disp_val=txt[:57]+"..."if len(txt)>60 else txt
            pop_msg=f"Copied {desc}:\n{disp_val}"if desc and desc!="all values"else f"Copied: {desc}"
            if not desc:pop_msg=f"Copied:\n{disp_val}"
            parent_for_popup = self if self.isVisible() else None
            InfoPopupWindow(pop_msg,parent_for_popup,2000).show()
        else: InfoPopupWindow("Error: Clipboard not accessible.",self if self.isVisible()else None,3000).show()

    @Slot()
    def copy_all_values_to_clipboard(self):
        lines=[f"RGB: {self._format_rgb()}",f"RGBA: {self._format_rgba()}",f"HTML: {self._format_html()}",
                 f"HEX ARGB: {self._format_hex_argb()}",f"HSL(Win): {self._format_hsl_for_copy()}",
                 f"HSV: {self._format_hsv_for_copy()}",f"CMYK: {self._format_cmyk_for_copy()}",
                 f"Decimal: {self._format_decimal_qrgb()}"]
        self.copy_to_clipboard("\n".join(lines),"all values")

    def get_selected_color(self)->QColor:return QColor(self.sel_color)

    @Slot(QColor)
    def handle_palette_color_cell_clicked(self,c:QColor):
        if c.isValid():
            self.c_dialog_w.setCurrentColor(c)
            if self.clip:self.clip.setText(f"{c.red()},{c.green()},{c.blue()}")
            found_ext=send_rgb_values_to_external_dialog(c.red(),c.green(),c.blue(),self, False) 
            if found_ext:InfoPopupWindow(f"Color sent to System Color Dialog.",self,2000).show() 

    @Slot(int)
    def handle_request_save_color_to_palette_cell(self,cell_idx:int):
        log_message(f"Generic save request for cell {cell_idx} - should be handled by a dedicated handler.")

if __name__=="__main__":
    EXECUTABLE_NAME = "WindowsScreenColorCopyPaste.exe"
    log_message(f"Starting application. Executable name to check: {EXECUTABLE_NAME}")
    
    # kill_lingering_processes_by_name(EXECUTABLE_NAME) # Uncomment if needed

    app=QApplication(sys.argv)
    # QApplication.setApplicationName("WindowsScreenColorCopyPaste") # Already done by QSettings
    # QApplication.setOrganizationName("ColorPasteOrg") # Already done by QSettings
    app.setQuitOnLastWindowClosed(False) 

    # Load the application icon once
    global_app_icon = load_application_icon(ICON_FILE_NAME)
    if not global_app_icon.isNull():
        app.setWindowIcon(global_app_icon) # Set for the entire application
        log_message("Global application icon has been set using loaded icon (expected in APP_BASE_PATH).")
    else:
        log_message("Global application icon remains default (no valid icon found/loaded for app from APP_BASE_PATH or fallbacks).")

    start_c=QColor(189,100,165)
    # Pass the loaded icon to the dialog
    dlg=CustomColorPickerDialog(initial_color=start_c, app_icon=global_app_icon)

    dlg.show()
    log_message("--- colorPASTE: Starting main application event loop ---")

    exit_code = app.exec()

    log_message(f"--- colorPASTE: Main application event loop finished with code: {exit_code} ---")
    log_message(f"--- colorPASTE: Calling sys.exit({exit_code}) ---")
    sys.exit(exit_code)