import tkinter as tk
import unittest

from scraper_app import ScraperApp, dispatch_edit_history_event, supports_edit_history


class FakeShortcutHost:
    def __init__(self, focused_widget: object) -> None:
        self.focused_widget = focused_widget

    def focus_get(self) -> object:
        return self.focused_widget

    _dispatch_focus_history_event = ScraperApp._dispatch_focus_history_event


class EditHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable for test run: {exc}")
        self.root.withdraw()

    def tearDown(self) -> None:
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.destroy()

    def test_supports_edit_history_detects_supported_widgets(self) -> None:
        text_widget = tk.Text(self.root, undo=True)
        entry_widget = tk.Entry(self.root)
        self.assertTrue(supports_edit_history(text_widget))
        self.assertTrue(supports_edit_history(entry_widget))

    def test_supports_edit_history_rejects_non_widgets(self) -> None:
        self.assertFalse(supports_edit_history(object()))

    def test_supports_edit_history_rejects_destroyed_widgets(self) -> None:
        widget = tk.Text(self.root, undo=True)
        widget.destroy()
        self.assertFalse(supports_edit_history(widget))

    def test_dispatch_edit_history_event_undo_redo_round_trip_for_text_widget(self) -> None:
        widget = tk.Text(self.root, undo=True, autoseparators=True)
        widget.insert("1.0", "hello")
        widget.edit_separator()
        widget.delete("1.4", "1.5")
        widget.edit_separator()
        self.assertEqual(widget.get("1.0", "end-1c"), "hell")

        self.assertTrue(dispatch_edit_history_event(widget, "<<Undo>>"))
        self.assertEqual(widget.get("1.0", "end-1c"), "hello")

        self.assertTrue(dispatch_edit_history_event(widget, "<<Redo>>"))
        self.assertEqual(widget.get("1.0", "end-1c"), "hell")

    def test_dispatch_edit_history_event_ignores_non_edit_widget(self) -> None:
        frame = tk.Frame(self.root)
        self.assertFalse(dispatch_edit_history_event(frame, "<<Undo>>"))

    def test_shortcut_methods_break_only_when_edit_history_dispatches(self) -> None:
        widget = tk.Text(self.root, undo=True, autoseparators=True)
        widget.insert("1.0", "hello")
        widget.edit_separator()
        widget.delete("1.4", "1.5")
        widget.edit_separator()
        host = FakeShortcutHost(widget)

        self.assertEqual(ScraperApp._shortcut_undo(host, None), "break")
        self.assertEqual(widget.get("1.0", "end-1c"), "hello")

        self.assertEqual(ScraperApp._shortcut_redo(host, None), "break")
        self.assertEqual(widget.get("1.0", "end-1c"), "hell")

        non_edit_host = FakeShortcutHost(tk.Frame(self.root))
        self.assertIsNone(ScraperApp._shortcut_undo(non_edit_host, None))
        self.assertIsNone(ScraperApp._shortcut_redo(non_edit_host, None))


if __name__ == "__main__":
    unittest.main()
