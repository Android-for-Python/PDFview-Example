from kivy.app import App
from kivy.uix.button import Button
from android.storage import app_storage_path
import requests
from threading import Thread
from pdfview import PdfView

# For details see pdfview.py 

# Testing (but not pdfview) requires:
# android.permissions = INTERNET
# add to requirements : requests,urllib3,chardet,idna
# Tested on 19c/27 , 19c/30, and 21d/30

class MyApp(App):
    def build(self):
        self.pdfview = None
        Thread(target=self.download_test_pdf,daemon=True).start()
        return Button(text= 'Tap for PDF', on_press = self.view_pdf)

    def download_test_pdf(self):
        self.target = join(app_storage_path(),'day5.pdf')
        r = requests.get('http://www.planckvacuum.com/pdf/day5.pdf')
        with open(self.target, 'wb') as fd:
            for chunk in r.iter_content(chunk_size=128):
                fd.write(chunk)

    def view_pdf(self,b):
        if self.target:
            self.pdfview = PdfView(self.target)

    def on_resume(self):
        if self.pdfview:
            self.pdfview.resume()
        
        
MyApp().run()

