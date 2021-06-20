# Android *only* PDF Viewer for Kivy, *full screen only*.
#
# Swipe left or right to change page in pdf
# Back key or back gesture returns the view to the Kivy layout before PdfView()
# Rotates document if buildozer.spec orientation = all
# Document width fits screen width, vertical scroll added if necessary.
# NOTE: self.resume() must be called on_resume() if orientation = all
#
# Base Class:  https://kivy.org/doc/stable/api-kivy.uix.modalview.html
# The contents of this ModalView are Android Views, not Kivy Widgets. Inside
# this ModalView Kivy does not paint the screen or get touch events from the
# screen. Painting and touch handling are done using the Android Java API via
# Pyjnius.
#
# Uses buildozer.spec:
#   orientation = landscape, portrait, or all
# Argument:
#   filepath : required string, path to pdf file
#
# Issues:
#   no pinch/zoom/drag, so 'orientation = all' is a good choice
#
# Source https://github.com/Android-for-Python/PDFview-Example

from kivy.uix.modalview import ModalView
from kivy.clock import Clock
from kivy.core.window import Window
from android.runnable import run_on_ui_thread
from jnius import autoclass, cast, PythonJavaClass, java_method
from os.path import exists

PdfRenderer = autoclass('android.graphics.pdf.PdfRenderer')
ParcelFileDescriptor = autoclass('android.os.ParcelFileDescriptor')
Page = autoclass('android.graphics.pdf.PdfRenderer$Page')
Bitmap = autoclass('android.graphics.Bitmap')
BitmapConfig = autoclass('android.graphics.Bitmap$Config')
ImageView = autoclass('android.widget.ImageView')
ViewGroup = autoclass('android.view.ViewGroup')
ScrollView = autoclass('android.widget.ScrollView') 
PythonActivity = autoclass('org.kivy.android.PythonActivity')
LayoutParams = autoclass('android.view.ViewGroup$LayoutParams')
LinearLayout = autoclass('android.widget.LinearLayout')
File = autoclass('java.io.File')
Canvas = autoclass('android.graphics.Canvas')
KeyEvent = autoclass('android.view.KeyEvent')
MotionEvent = autoclass('android.view.MotionEvent')
Gravity = autoclass('android.view.Gravity')
GestureDetector = autoclass('android.view.GestureDetector')

class GestureListener(PythonJavaClass):
    __javacontext__ = 'app'
    __javainterfaces__ = ['android/view/GestureDetector$OnGestureListener']

    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    @java_method('(Landroid/view/MotionEvent;)Z')
    def onDown(self,e):
        return False

    @java_method('(Landroid/view/MotionEvent;)V')
    def onShowPress(self,e):
        pass

    @java_method('(Landroid/view/MotionEvent;)Z')
    def onSingleTapUp(self,e):
        return False

    @java_method('(Landroid/view/MotionEvent;Landroid/view/MotionEvent;FF)Z')
    def onScroll(self,e1, e2, distanceX, distanceY):
        SWIPE_THRESHOLD = 100
        result = False
        if self.callback:
            if abs(distanceY) > abs(distanceX):
                if abs(distanceY) < SWIPE_THRESHOLD:
                    self.callback('Scroll',distanceY)
                    result = True
        return result

    @java_method('(Landroid/view/MotionEvent;)V')
    def onLongPress(self,e):
        pass

    @java_method('(Landroid/view/MotionEvent;Landroid/view/MotionEvent;FF)Z')
    def onFling(self, e1, e2, velocityX, velocityY):
        SWIPE_THRESHOLD = 100
        SWIPE_VELOCITY_THRESHOLD = 100
        result = False
        diffY = e2.getY() - e1.getY()
        diffX = e2.getX() - e1.getX()
        if self.callback:
            if abs(diffX) > abs(diffY) and\
               abs(diffX) > SWIPE_THRESHOLD and\
               abs(velocityX) > SWIPE_VELOCITY_THRESHOLD:
                if diffX > 0:
                    self.callback('SwipeRight',0)
                else:
                    self.callback('SwipeLeft',0)
                result = True
            elif abs(diffY) > abs(diffX) and\
                 abs(diffY) > SWIPE_THRESHOLD and\
                 abs(velocityY) > SWIPE_VELOCITY_THRESHOLD:
                self.callback('Fling',velocityY)
                result = True
        return result


class TouchListener(PythonJavaClass):
    __javacontext__ = 'app'
    __javainterfaces__ = ['android/view/View$OnTouchListener']

    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.context =  PythonActivity.mActivity.getApplicationContext()
        self.gesture_listener = GestureListener(self.callback)
        self.gesture_detector = GestureDetector(self.context,
                                                self.gesture_listener)
 
    @java_method('(Landroid/view/View;Landroid/view/MotionEvent;)Z')
    def onTouch(self, v, event):
        # onTouch() returns False when events consumed  !!! wrong
        # onTouchEvent() returns True when matched
        return not self.gesture_detector.onTouchEvent(event)


class KeyListener(PythonJavaClass):
    __javacontext__ = 'app'
    __javainterfaces__ = ['android/view/View$OnKeyListener']

    def __init__(self, on_dismiss):
        super().__init__()
        self.on_dismiss = on_dismiss

    @java_method('(Landroid/view/View;ILandroid/view/KeyEvent;)Z')
    def onKey(self, v, key_code, event):
        if event.getAction() == KeyEvent.ACTION_DOWN and\
           key_code == KeyEvent.KEYCODE_BACK: 
            self.on_dismiss()
            return True
        return False
        
        
class PdfView(ModalView):
    # https://developer.android.com/reference/android/graphics/pdf/PdfRenderer.html

    def __init__(self, filepath, **kwargs):
        super().__init__(**kwargs)
        self.enable_dismiss = True
        self.filepath = filepath
        self.layout = None
        self.imgview = None
        self.bitmap = None
        self.render = None
        self.page = 0
        if exists(filepath):
            self.open()
        else:
            print('PdfView: '+filepath+' does not exist.')
            self.dismiss()
            
    def on_open(self):
        self._build_layout()
        self._display_current_page()
        self._instantiate()

    def on_dismiss(self):
        if self.enable_dismiss:
            self.enable_dismiss = False
            self._destroy_render()
            self._destroy_layout()

    def on_size(self, instance, size):
        self._display_current_page()

    def resume(self):
        # In case the device is rotated between pause and resume
        self._display_current_page()
            
    def _create_render(self):
        pfd = ParcelFileDescriptor.open(File(self.filepath),
                                        ParcelFileDescriptor.MODE_READ_ONLY) 
        self.render = PdfRenderer(pfd)

    def _destroy_render(self):
        if self.render:
            self.render.close()

    def _display_current_page(self):
        if not self.render:
            self._create_render()
        tmp = self.bitmap
        page = self.render.openPage(self.page)
        height = int(Window.width * page.getHeight() / page.getWidth())
        bitmap = Bitmap.createBitmap(Window.width, height,
                                     BitmapConfig.ARGB_8888)
        mutable = bitmap.copy(BitmapConfig.ARGB_8888,True)
        del bitmap
        canvas = Canvas(mutable)
        canvas.drawARGB(255, 255, 255, 255)
        page.render(mutable, None, None, Page.RENDER_MODE_FOR_DISPLAY)
        page.close()
        self.bitmap = mutable
        self._set_image_bitmap()
        if tmp:
            del tmp    

    def _touch_action(self,action,param):
        if action == 'SwipeRight':
            self.page = max(self.page-1,0)
            self._display_current_page()
        elif action == 'SwipeLeft':
            self.page = min(self.page+1,self.render.getPageCount()-1)
            self._display_current_page()
        elif action == 'Fling':
            self._fling(-param)
        elif action == 'Scroll':
            self._scroll(param) 

    @run_on_ui_thread        
    def _build_layout(self):
        mActivity = PythonActivity.mActivity 
        context =  mActivity.getApplicationContext()
        imgview = ImageView(context)
        scrollview = ScrollView(context)
        scrollview.addView(imgview)
        layout = LinearLayout(mActivity)
        layout.setOrientation(LinearLayout.VERTICAL)
        layout.setVerticalGravity(Gravity.CENTER_VERTICAL)
        layout.addView(scrollview)
        self.layout = layout
        self.imgview = imgview
        self.scrollview = scrollview

    @run_on_ui_thread        
    def _instantiate(self):
        mActivity = PythonActivity.mActivity 
        mActivity.addContentView(self.layout, LayoutParams(-1,-1))
        self.key_listener = KeyListener(self.dismiss)
        self.touch_listener = TouchListener(self._touch_action)
        self.imgview.setOnKeyListener(self.key_listener)
        self.scrollview.setOnTouchListener(self.touch_listener)
        
    @run_on_ui_thread        
    def _destroy_layout(self):
        if self.layout:
            parent = cast(ViewGroup, self.layout.getParent())
            if parent is not None: parent.removeView(self.layout)

    @run_on_ui_thread
    def _fling(self,velocityY):
        if self.scrollview:
            self.scrollview.fling(velocityY)

    @run_on_ui_thread
    def _scroll(self,distanceY):
        if self.scrollview:
            self.scrollview.smoothScrollBy(0,distanceY)

    @run_on_ui_thread
    def _set_image_bitmap(self):
        if self.imgview:
            self.imgview.setImageBitmap(self.bitmap)
        
            
            
