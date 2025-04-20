import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, 
                            QWidget, QTextEdit, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key from environment
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')
if not CLAUDE_API_KEY:
    print("Error: CLAUDE_API_KEY not found in environment variables")
    sys.exit(1)

class AutocompleteTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_updating = False
        self.current_suggestion = ""
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)
        self.setPlaceholderText("Type here to see suggestions...")
        self.setStyleSheet("""
            QTextEdit {
                padding: 10px;
                font-size: 14px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
                color: black;
            }
        """)

    def setSuggestion(self, suggestion):
        if self.is_updating:
            return
        
        try:
            self.is_updating = True
            current_text = self.toPlainText()
            if suggestion and suggestion.startswith(current_text):
                self.current_suggestion = suggestion
                self.setText(suggestion)
                cursor = self.textCursor()
                cursor.setPosition(len(current_text))
                cursor.setPosition(len(suggestion), cursor.MoveMode.KeepAnchor)
                self.setTextCursor(cursor)
        finally:
            self.is_updating = False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Tab and self.current_suggestion:
            # Accept suggestion
            event.accept()
            self.is_updating = True
            self.setText(self.current_suggestion)
            cursor = self.textCursor()
            cursor.setPosition(len(self.current_suggestion))
            self.setTextCursor(cursor)
            self.current_suggestion = ""
            self.is_updating = False
        elif event.key() == Qt.Key.Key_Return and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Allow new lines only with Ctrl+Enter
            super().keyPressEvent(event)
        elif event.key() == Qt.Key.Key_Return:
            # Regular Enter updates the suggestion
            event.accept()
        else:
            super().keyPressEvent(event)

class SuggestionWorker(QThread):
    suggestion_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, text):
        super().__init__()
        self.text = text
        
    def run(self):
        try:
            headers = {
                "Content-Type": "application/json",
                "x-api-key": CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01"
            }
            
            data = {
                "model": "claude-3-haiku-20240307",
                "messages": [{
                    "role": "user",
                    "content": f"Complete this text naturally (continue exactly where it left off, no introduction): {self.text}"
                }],
                "max_tokens": 50,
                "temperature": 0.7,
                "system": "You are a helpful text completion assistant. Only provide direct continuations of the text, no explanations or introductions."
            }
            
            print("Sending API request with data:", data)
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=data
            )
            
            print("Response status:", response.status_code)
            print("Response headers:", response.headers)
            
            if response.status_code == 200:
                result = response.json()
                print("API Response:", result)
                suggestion = result['content'][0]['text'].strip()
                self.suggestion_ready.emit(self.text + suggestion)
            else:
                try:
                    error_details = response.json()
                    error_msg = f"API Error ({response.status_code}): {error_details}"
                except:
                    error_msg = f"API Error ({response.status_code}): {response.text}"
                print(error_msg)
                self.error_occurred.emit(error_msg)
                
        except Exception as e:
            error_msg = f"Error getting suggestion: {str(e)}"
            print(error_msg)
            self.error_occurred.emit(error_msg)

class AutocompleteWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Claude Autocomplete")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create input field
        self.input_field = AutocompleteTextEdit()
        self.input_field.textChanged.connect(self.on_text_changed)
        layout.addWidget(self.input_field)
        
        # Create status label
        self.status_label = QLabel("Type to see suggestions. Press Tab to accept. Use Ctrl+Enter for new lines.")
        self.status_label.setStyleSheet("color: #666; font-size: 12px; padding: 5px;")
        layout.addWidget(self.status_label)
        
        # Set window properties
        self.setMinimumSize(600, 400)
        
        # Initialize suggestion worker
        self.suggestion_worker = None
        
        print("Application started. Type in the input field to see suggestions.")
        print("Press Tab to accept a suggestion. Use Ctrl+Enter for new lines.")

    def on_text_changed(self):
        text = self.input_field.toPlainText()
        if len(text) >= 3 and not self.input_field.is_updating:
            print(f"Getting suggestion for: {text}")
            self.status_label.setText("Getting suggestion...")
            
            # Cancel previous worker if it exists
            if self.suggestion_worker and self.suggestion_worker.isRunning():
                self.suggestion_worker.terminate()
                self.suggestion_worker.wait()
            
            # Create and start new worker
            self.suggestion_worker = SuggestionWorker(text)
            self.suggestion_worker.suggestion_ready.connect(self.on_suggestion_ready)
            self.suggestion_worker.error_occurred.connect(self.on_error)
            self.suggestion_worker.start()

    @pyqtSlot(str)
    def on_suggestion_ready(self, suggestion):
        self.input_field.setSuggestion(suggestion)
        self.status_label.setText("Type to see suggestions. Press Tab to accept. Use Ctrl+Enter for new lines.")

    @pyqtSlot(str)
    def on_error(self, error_msg):
        self.status_label.setText(f"Error: {error_msg}")
        QMessageBox.warning(self, "API Error", error_msg)

def main():
    # Check for API key before starting the app
    if not CLAUDE_API_KEY:
        QMessageBox.critical(None, "Configuration Error", 
                           "CLAUDE_API_KEY not found in environment variables.\n"
                           "Please add it to your .env file.")
        return

    app = QApplication(sys.argv)
    window = AutocompleteWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 