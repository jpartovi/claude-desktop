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
        self.setMinimumWidth(200)
        self.setMaximumWidth(400)
        self.setMinimumHeight(40)
        self.setMaximumHeight(400)
        self.setPlaceholderText("Type for suggestions (Tab to accept)")
        self.document().documentLayout().documentSizeChanged.connect(self.adjust_height)
        
        font = QFont("Helvetica Neue", 14)
        self.setFont(font)
        
        self.setStyleSheet("""
            QTextEdit {
                padding: 8px 12px;
                border: 1.5px solid #e0e0e0;
                border-radius: 12px;
                background-color: rgba(255, 255, 255, 0.95);
                color: #2c3e50;
                selection-background-color: #bdc3c7;
            }
            QTextEdit:focus {
                border: 1.5px solid #3498db;
                background-color: white;
            }
        """)

    def adjust_height(self):
        doc_height = self.document().size().height()
        margins = self.contentsMargins()
        required_height = doc_height + margins.top() + margins.bottom() + 20
        new_height = max(40, min(required_height, 400))
        self.setFixedHeight(int(new_height))
        if self.window():
            self.window().adjustSize()

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
                    "content": f"The user is typing and their cursor is at the end of this text. Complete it naturally from exactly where it ends, with no extra spaces: {self.text}<cursor>"
                }],
                "max_tokens": 50,
                "temperature": 0.1,
                "system": """You are an autocomplete assistant. 
                Your task is to continue text from exactly where 
                the cursor is positioned. complete around 4-5 words, 
                finishing the current word if necessary, and if not, 
                starting a new word, or finishing a sentence, adding 
                punctuation, whatever is appropriate. Make sure to add 
                spaces between the completion and the original text if 
                necessary so that original+completion is a coherent 
                sentence. The completion should also never repeat the 
                text that came before so that it can be seamlessly 
                tacked on to the end of the original text.
                """
            }
            
            # Add timeout to prevent stalls
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=data,
                timeout=5.0  # 5 second timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                suggestion = result['content'][0]['text'].strip()
                
                # Remove the cursor marker if it's in the response
                suggestion = suggestion.replace('<cursor>', '')
                
                # Clean up the suggestion
                if suggestion.startswith(self.text):
                    suggestion = suggestion[len(self.text):]
                suggestion = suggestion.lstrip()
                
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
                
        except requests.exceptions.Timeout:
            print("API request timed out after 5 seconds")
            self.error_occurred.emit("Request timed out")
        except Exception as e:
            error_msg = f"Error getting suggestion: {str(e)}"
            print(error_msg)
            self.error_occurred.emit(error_msg)

class AutocompleteWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Claude")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Create input field directly as central widget
        self.input_field = AutocompleteTextEdit()
        self.input_field.textChanged.connect(self.on_text_changed)
        self.setCentralWidget(self.input_field)
        
        # Center on screen
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.center() - self.rect().center())
        
        # Initialize suggestion worker
        self.suggestion_worker = None
        
        # Set window shadow and opacity
        self.setStyleSheet("""
            QMainWindow {
                background-color: transparent;
            }
        """)

    def adjustSize(self):
        if self.input_field:
            # Set window size to match text box exactly
            self.setFixedSize(self.input_field.size())

    def on_text_changed(self):
        text = self.input_field.toPlainText()
        if len(text) >= 3 and not self.input_field.is_updating:
            # Cancel previous worker if it exists
            if self.suggestion_worker and self.suggestion_worker.isRunning():
                print("Cancelling previous suggestion worker")
                self.suggestion_worker.terminate()
                self.suggestion_worker.wait()
            
            print(f"Starting new suggestion worker for text: {text}")
            # Create and start new worker
            self.suggestion_worker = SuggestionWorker(text)
            self.suggestion_worker.suggestion_ready.connect(self.on_suggestion_ready)
            self.suggestion_worker.error_occurred.connect(self.on_error)
            self.suggestion_worker.start()

    @pyqtSlot(str)
    def on_suggestion_ready(self, suggestion):
        print(f"Received suggestion: {suggestion}")
        self.input_field.setSuggestion(suggestion)

    @pyqtSlot(str)
    def on_error(self, error_msg):
        print(f"Error: {error_msg}")
        # Clear any partial suggestions
        if self.input_field.current_suggestion:
            self.input_field.current_suggestion = ""
            self.input_field.setText(self.input_field.current_text)

    def mousePressEvent(self, event):
        self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        delta = event.globalPosition().toPoint() - self.oldPos
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPosition().toPoint()

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