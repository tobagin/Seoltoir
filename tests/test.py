import gi
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio

class TestApp(Adw.Application):
    def do_activate(self):
        print("TestApp do_activate called")

app = TestApp(application_id="io.github.tobagin.seoltoir")
app.run([])