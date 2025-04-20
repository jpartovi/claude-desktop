import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, 
                            QWidget, QTextEdit, QMessageBox, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont, QPalette, QColor
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key from environment
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')
if not CLAUDE_API_KEY:
    print("Error: CLAUDE_API_KEY not found in environment variables")
    sys.exit(1)

class ModernFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            ModernFrame {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
        """)

class AutocompleteTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_updating = False
        self.current_suggestion = ""
        self.current_text = ""
        self.setMinimumWidth(600)
        self.setMinimumHeight(200)
        self.setPlaceholderText("Type here to see suggestions...")
        
        # Set font
        font = QFont("SF Pro Display, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Oxygen, Ubuntu, Cantarell, Open Sans, Helvetica Neue, sans-serif", 14)
        self.setFont(font)
        
        self.setStyleSheet("""
            QTextEdit {
                padding: 15px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                background-color: #ffffff;
                color: #2c3e50;
                selection-background-color: #bdc3c7;
            }
            QTextEdit:focus {
                border: 2px solid #3498db;
            }
        """)

    def setSuggestion(self, suggestion):
        if self.is_updating:
            return
        
        try:
            self.is_updating = True
            current_text = self.toPlainText()
            self.current_text = current_text
            
            # Only show the new part of the suggestion
            if suggestion and suggestion.startswith(current_text):
                new_text = suggestion[len(current_text):]
                if new_text:
                    self.current_suggestion = suggestion
                    self.setText(current_text + new_text)
                    cursor = self.textCursor()
                    cursor.setPosition(len(current_text))
                    cursor.setPosition(len(current_text) + len(new_text), cursor.MoveMode.KeepAnchor)
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
            self.current_text = ""
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
        
    def clean_suggestion(self, suggestion):
        """Clean up the suggestion."""
        # Remove any duplicate text from the start
        if suggestion.startswith(self.text):
            suggestion = suggestion[len(self.text):].lstrip()
        return suggestion
        
    def run(self):
        try:
            headers = {
                "Content-Type": "application/json",
                "x-api-key": CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01"
            }
            
            # Analyze if we're mid-word
            words = self.text.split()
            is_mid_word = len(words) > 0 and not self.text.endswith(' ')
            last_word = words[-1] if words else ""
            
            if is_mid_word:
                prompt = f"Complete this word or phrase naturally: {last_word}"
            else:
                prompt = f"Continue this text naturally with 2-5 words: {self.text}"
            
            data = {
                "model": "claude-3-haiku-20240307",
                "messages": [{
                    "role": "user",
                    "content": prompt
                }],
                "max_tokens": 20,
                "temperature": 0.7,
                "system": """You are a text completion assistant. Follow these rules strictly:
1. If completing a partial word, only provide the rest of that word
2. If continuing after a complete word, include appropriate spacing
3. Never repeat what was already typed
4. Provide natural, contextual continuations
5. Keep responses very brief (2-5 words)"""
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
                
                # Clean up the suggestion
                suggestion = self.clean_suggestion(suggestion)
                
                # Only emit if we have a meaningful suggestion
                if suggestion:
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
        
        # Set window background
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f6fa;
            }
        """)
        
        # Create main container with padding
        container = QWidget()
        self.setCentralWidget(container)
        
        # Create outer layout with padding
        outer_layout = QVBoxLayout(container)
        outer_layout.setContentsMargins(20, 20, 20, 20)
        outer_layout.setSpacing(15)
        
        # Create title label
        title_label = QLabel("Claude Autocomplete")
        title_label.setStyleSheet("""
            QLabel {
                color: #2c3e50;
                font-size: 24px;
                font-weight: bold;
                margin-bottom: 10px;
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer_layout.addWidget(title_label)
        
        # Create description label
        desc_label = QLabel("Get AI-powered text suggestions as you type")
        desc_label.setStyleSheet("""
            QLabel {
                color: #7f8c8d;
                font-size: 14px;
                margin-bottom: 20px;
            }
        """)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer_layout.addWidget(desc_label)
        
        # Create modern frame for input area
        input_frame = ModernFrame()
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(15, 15, 15, 15)
        input_layout.setSpacing(10)
        
        # Create input field
        self.input_field = AutocompleteTextEdit()
        self.input_field.textChanged.connect(self.on_text_changed)
        input_layout.addWidget(self.input_field)
        
        # Create status label with modern styling
        self.status_label = QLabel("Type to see suggestions • Press Tab to accept • Use Ctrl+Enter for new lines")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #7f8c8d;
                font-size: 12px;
                padding: 5px;
                background-color: #f8f9fa;
                border-radius: 4px;
            }
        """)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        input_layout.addWidget(self.status_label)
        
        # Add input frame to outer layout
        outer_layout.addWidget(input_frame)
        
        # Set window properties
        self.setMinimumSize(700, 500)
        
        # Initialize suggestion worker
        self.suggestion_worker = None
        
        print("Application started. Type in the input field to see suggestions.")
        print("Press Tab to accept a suggestion. Use Ctrl+Enter for new lines.")

    def set_status(self, message, is_error=False):
        style = """
            QLabel {
                color: %s;
                font-size: 12px;
                padding: 8px;
                background-color: %s;
                border-radius: 4px;
                border: 1px solid %s;
            }
        """ % (
            "#e74c3c" if is_error else "#7f8c8d",  # text color
            "#fdf3f2" if is_error else "#f8f9fa",  # background color
            "#fadbd8" if is_error else "#f8f9fa",  # border color
        )
        self.status_label.setStyleSheet(style)
        self.status_label.setText(message)

    def on_text_changed(self):
        text = self.input_field.toPlainText()
        if len(text) >= 3 and not self.input_field.is_updating:
            print(f"Getting suggestion for: {text}")
            self.set_status("Getting suggestion...")
            
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
        self.set_status("Type to see suggestions • Press Tab to accept • Use Ctrl+Enter for new lines")

    @pyqtSlot(str)
    def on_error(self, error_msg):
        self.set_status(f"Error: {error_msg}", is_error=True)
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