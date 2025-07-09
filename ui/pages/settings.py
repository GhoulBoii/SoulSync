from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                           QFrame, QPushButton, QLineEdit, QComboBox,
                           QCheckBox, QSpinBox, QTextEdit, QGroupBox, QFormLayout, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from config.settings import config_manager

class SettingsGroup(QGroupBox):
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.setStyleSheet("""
            QGroupBox {
                background: #282828;
                border: 1px solid #404040;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                color: #ffffff;
                padding-top: 15px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)

class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = None
        self.form_inputs = {}
        self.setup_ui()
        self.load_config_values()
    
    def setup_ui(self):
        self.setStyleSheet("""
            SettingsPage {
                background: #191414;
            }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(25)
        
        # Header
        header = self.create_header()
        main_layout.addWidget(header)
        
        # Settings content
        content_layout = QHBoxLayout()
        content_layout.setSpacing(30)
        
        # Left column
        left_column = self.create_left_column()
        content_layout.addWidget(left_column)
        
        # Right column
        right_column = self.create_right_column()
        content_layout.addWidget(right_column)
        
        main_layout.addLayout(content_layout)
        main_layout.addStretch()
        
        # Save button
        self.save_btn = QPushButton("💾 Save Settings")
        self.save_btn.setFixedHeight(45)
        self.save_btn.clicked.connect(self.save_settings)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background: #1db954;
                border: none;
                border-radius: 22px;
                color: #000000;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #1ed760;
            }
        """)
        
        main_layout.addWidget(self.save_btn)
    
    def load_config_values(self):
        """Load current configuration values into form inputs"""
        try:
            # Load Spotify config
            spotify_config = config_manager.get_spotify_config()
            self.client_id_input.setText(spotify_config.get('client_id', ''))
            self.client_secret_input.setText(spotify_config.get('client_secret', ''))
            
            # Load Plex config
            plex_config = config_manager.get_plex_config()
            self.plex_url_input.setText(plex_config.get('base_url', ''))
            self.plex_token_input.setText(plex_config.get('token', ''))
            
            # Load Soulseek config
            soulseek_config = config_manager.get_soulseek_config()
            self.slskd_url_input.setText(soulseek_config.get('slskd_url', ''))
            self.api_key_input.setText(soulseek_config.get('api_key', ''))
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load configuration: {e}")
    
    def save_settings(self):
        """Save current form values to configuration"""
        try:
            # Save Spotify settings
            config_manager.set('spotify.client_id', self.client_id_input.text())
            config_manager.set('spotify.client_secret', self.client_secret_input.text())
            
            # Save Plex settings
            config_manager.set('plex.base_url', self.plex_url_input.text())
            config_manager.set('plex.token', self.plex_token_input.text())
            
            # Save Soulseek settings
            config_manager.set('soulseek.slskd_url', self.slskd_url_input.text())
            config_manager.set('soulseek.api_key', self.api_key_input.text())
            
            # Show success message
            QMessageBox.information(self, "Success", "Settings saved successfully!")
            
            # Update button text temporarily
            original_text = self.save_btn.text()
            self.save_btn.setText("✓ Saved!")
            self.save_btn.setStyleSheet("""
                QPushButton {
                    background: #1aa34a;
                    border: none;
                    border-radius: 22px;
                    color: #ffffff;
                    font-size: 14px;
                    font-weight: bold;
                }
            """)
            
            # Reset button after 2 seconds
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(2000, lambda: self.reset_save_button(original_text))
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")
    
    def reset_save_button(self, original_text):
        """Reset save button to original state"""
        self.save_btn.setText(original_text)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background: #1db954;
                border: none;
                border-radius: 22px;
                color: #000000;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #1ed760;
            }
        """)
    
    def test_spotify_connection(self):
        """Test Spotify API connection"""
        try:
            from core.spotify_client import SpotifyClient
            
            # Create temporary client with current form values
            temp_config = config_manager.get_spotify_config().copy()
            temp_config['client_id'] = self.client_id_input.text()
            temp_config['client_secret'] = self.client_secret_input.text()
            
            # Save temporarily to test
            original_client_id = config_manager.get('spotify.client_id')
            original_client_secret = config_manager.get('spotify.client_secret')
            
            config_manager.set('spotify.client_id', temp_config['client_id'])
            config_manager.set('spotify.client_secret', temp_config['client_secret'])
            
            # Test connection
            client = SpotifyClient()
            if client.is_authenticated():
                user_info = client.get_user_info()
                username = user_info.get('display_name', 'Unknown') if user_info else 'Unknown'
                QMessageBox.information(self, "Success", f"✓ Spotify connection successful!\nConnected as: {username}")
            else:
                QMessageBox.warning(self, "Failed", "✗ Spotify connection failed.\nCheck your credentials and try again.")
            
            # Restore original values
            config_manager.set('spotify.client_id', original_client_id)
            config_manager.set('spotify.client_secret', original_client_secret)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"✗ Spotify test failed:\n{str(e)}")
    
    def test_plex_connection(self):
        """Test Plex server connection"""
        try:
            from core.plex_client import PlexClient
            
            # Save temporarily to test
            original_base_url = config_manager.get('plex.base_url')
            original_token = config_manager.get('plex.token')
            
            config_manager.set('plex.base_url', self.plex_url_input.text())
            config_manager.set('plex.token', self.plex_token_input.text())
            
            # Test connection
            client = PlexClient()
            if client.is_connected():
                server_name = client.server.friendlyName if client.server else 'Unknown'
                QMessageBox.information(self, "Success", f"✓ Plex connection successful!\nServer: {server_name}")
            else:
                QMessageBox.warning(self, "Failed", "✗ Plex connection failed.\nCheck your server URL and token.")
            
            # Restore original values
            config_manager.set('plex.base_url', original_base_url)
            config_manager.set('plex.token', original_token)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"✗ Plex test failed:\n{str(e)}")
    
    def test_soulseek_connection(self):
        """Test Soulseek slskd connection"""
        try:
            import requests
            
            slskd_url = self.slskd_url_input.text()
            api_key = self.api_key_input.text()
            
            if not slskd_url:
                QMessageBox.warning(self, "Error", "Please enter slskd URL")
                return
            
            # Test API endpoint
            headers = {}
            if api_key:
                headers['X-API-Key'] = api_key
            
            response = requests.get(f"{slskd_url}/api/v0/session", headers=headers, timeout=5)
            
            if response.status_code == 200:
                QMessageBox.information(self, "Success", "✓ Soulseek connection successful!\nslskd is responding.")
            else:
                QMessageBox.warning(self, "Failed", f"✗ Soulseek connection failed.\nHTTP {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "Error", f"✗ Soulseek test failed:\n{str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"✗ Soulseek test failed:\n{str(e)}")
    
    def create_header(self):
        header = QWidget()
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Title
        title_label = QLabel("Settings")
        title_label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #ffffff;")
        
        # Subtitle
        subtitle_label = QLabel("Configure your music sync and download preferences")
        subtitle_label.setFont(QFont("Arial", 14))
        subtitle_label.setStyleSheet("color: #b3b3b3;")
        
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        
        return header
    
    def create_left_column(self):
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setSpacing(20)
        
        # API Configuration
        api_group = SettingsGroup("API Configuration")
        api_layout = QVBoxLayout(api_group)
        api_layout.setContentsMargins(20, 25, 20, 20)
        api_layout.setSpacing(15)
        
        # Spotify settings
        spotify_frame = QFrame()
        spotify_layout = QFormLayout(spotify_frame)
        spotify_layout.setSpacing(10)
        
        spotify_title = QLabel("Spotify")
        spotify_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        spotify_title.setStyleSheet("color: #1db954;")
        
        self.client_id_input = QLineEdit()
        self.client_id_input.setStyleSheet(self.get_input_style())
        self.form_inputs['spotify.client_id'] = self.client_id_input
        
        self.client_secret_input = QLineEdit()
        self.client_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.client_secret_input.setStyleSheet(self.get_input_style())
        self.form_inputs['spotify.client_secret'] = self.client_secret_input
        
        spotify_layout.addRow(spotify_title)
        spotify_layout.addRow("Client ID:", self.client_id_input)
        spotify_layout.addRow("Client Secret:", self.client_secret_input)
        
        # Plex settings
        plex_frame = QFrame()
        plex_layout = QFormLayout(plex_frame)
        plex_layout.setSpacing(10)
        
        plex_title = QLabel("Plex")
        plex_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        plex_title.setStyleSheet("color: #e5a00d;")
        
        self.plex_url_input = QLineEdit()
        self.plex_url_input.setStyleSheet(self.get_input_style())
        self.form_inputs['plex.base_url'] = self.plex_url_input
        
        self.plex_token_input = QLineEdit()
        self.plex_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.plex_token_input.setStyleSheet(self.get_input_style())
        self.form_inputs['plex.token'] = self.plex_token_input
        
        plex_layout.addRow(plex_title)
        plex_layout.addRow("Server URL:", self.plex_url_input)
        plex_layout.addRow("Token:", self.plex_token_input)
        
        # Soulseek settings
        soulseek_frame = QFrame()
        soulseek_layout = QFormLayout(soulseek_frame)
        soulseek_layout.setSpacing(10)
        
        soulseek_title = QLabel("Soulseek")
        soulseek_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        soulseek_title.setStyleSheet("color: #ff6b35;")
        
        self.slskd_url_input = QLineEdit()
        self.slskd_url_input.setStyleSheet(self.get_input_style())
        self.form_inputs['soulseek.slskd_url'] = self.slskd_url_input
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Enter your slskd API key")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setStyleSheet(self.get_input_style())
        self.form_inputs['soulseek.api_key'] = self.api_key_input
        
        soulseek_layout.addRow(soulseek_title)
        soulseek_layout.addRow("slskd URL:", self.slskd_url_input)
        soulseek_layout.addRow("API Key:", self.api_key_input)
        
        api_layout.addWidget(spotify_frame)
        api_layout.addWidget(plex_frame)
        api_layout.addWidget(soulseek_frame)
        
        # Test connections
        test_layout = QHBoxLayout()
        test_layout.setSpacing(10)
        
        test_spotify = QPushButton("Test Spotify")
        test_spotify.setFixedHeight(30)
        test_spotify.clicked.connect(self.test_spotify_connection)
        test_spotify.setStyleSheet(self.get_test_button_style())
        
        test_plex = QPushButton("Test Plex")
        test_plex.setFixedHeight(30)
        test_plex.clicked.connect(self.test_plex_connection)
        test_plex.setStyleSheet(self.get_test_button_style())
        
        test_soulseek = QPushButton("Test Soulseek")
        test_soulseek.setFixedHeight(30)
        test_soulseek.clicked.connect(self.test_soulseek_connection)
        test_soulseek.setStyleSheet(self.get_test_button_style())
        
        test_layout.addWidget(test_spotify)
        test_layout.addWidget(test_plex)
        test_layout.addWidget(test_soulseek)
        
        api_layout.addLayout(test_layout)
        
        layout.addWidget(api_group)
        layout.addStretch()
        
        return column
    
    def create_right_column(self):
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setSpacing(20)
        
        # Download Settings
        download_group = SettingsGroup("Download Settings")
        download_layout = QVBoxLayout(download_group)
        download_layout.setContentsMargins(20, 25, 20, 20)
        download_layout.setSpacing(15)
        
        # Quality preference
        quality_layout = QHBoxLayout()
        quality_label = QLabel("Preferred Quality:")
        quality_label.setStyleSheet("color: #ffffff; font-size: 12px;")
        
        quality_combo = QComboBox()
        quality_combo.addItems(["FLAC", "320 kbps MP3", "256 kbps MP3", "192 kbps MP3", "Any"])
        quality_combo.setCurrentText("FLAC")
        quality_combo.setStyleSheet(self.get_combo_style())
        
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(quality_combo)
        quality_layout.addStretch()
        
        # Max concurrent downloads
        concurrent_layout = QHBoxLayout()
        concurrent_label = QLabel("Max Concurrent Downloads:")
        concurrent_label.setStyleSheet("color: #ffffff; font-size: 12px;")
        
        concurrent_spin = QSpinBox()
        concurrent_spin.setRange(1, 10)
        concurrent_spin.setValue(5)
        concurrent_spin.setStyleSheet(self.get_spin_style())
        
        concurrent_layout.addWidget(concurrent_label)
        concurrent_layout.addWidget(concurrent_spin)
        concurrent_layout.addStretch()
        
        # Download timeout
        timeout_layout = QHBoxLayout()
        timeout_label = QLabel("Download Timeout (seconds):")
        timeout_label.setStyleSheet("color: #ffffff; font-size: 12px;")
        
        timeout_spin = QSpinBox()
        timeout_spin.setRange(30, 600)
        timeout_spin.setValue(300)
        timeout_spin.setStyleSheet(self.get_spin_style())
        
        timeout_layout.addWidget(timeout_label)
        timeout_layout.addWidget(timeout_spin)
        timeout_layout.addStretch()
        
        # Download path
        path_layout = QHBoxLayout()
        path_label = QLabel("Download Path:")
        path_label.setStyleSheet("color: #ffffff; font-size: 12px;")
        
        path_input = QLineEdit("./downloads")
        path_input.setStyleSheet(self.get_input_style())
        
        browse_btn = QPushButton("Browse")
        browse_btn.setFixedSize(70, 30)
        browse_btn.setStyleSheet(self.get_test_button_style())
        
        path_layout.addWidget(path_label)
        path_layout.addWidget(path_input)
        path_layout.addWidget(browse_btn)
        
        download_layout.addLayout(quality_layout)
        download_layout.addLayout(concurrent_layout)
        download_layout.addLayout(timeout_layout)
        download_layout.addLayout(path_layout)
        
        # Sync Settings
        sync_group = SettingsGroup("Sync Settings")
        sync_layout = QVBoxLayout(sync_group)
        sync_layout.setContentsMargins(20, 25, 20, 20)
        sync_layout.setSpacing(15)
        
        # Auto-sync checkbox
        auto_sync = QCheckBox("Auto-sync playlists every hour")
        auto_sync.setChecked(True)
        auto_sync.setStyleSheet(self.get_checkbox_style())
        
        # Sync interval
        interval_layout = QHBoxLayout()
        interval_label = QLabel("Sync Interval (minutes):")
        interval_label.setStyleSheet("color: #ffffff; font-size: 12px;")
        
        interval_spin = QSpinBox()
        interval_spin.setRange(5, 1440)  # 5 minutes to 24 hours
        interval_spin.setValue(60)
        interval_spin.setStyleSheet(self.get_spin_style())
        
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(interval_spin)
        interval_layout.addStretch()
        
        sync_layout.addWidget(auto_sync)
        sync_layout.addLayout(interval_layout)
        
        # Logging Settings
        logging_group = SettingsGroup("Logging Settings")
        logging_layout = QVBoxLayout(logging_group)
        logging_layout.setContentsMargins(20, 25, 20, 20)
        logging_layout.setSpacing(15)
        
        # Log level
        log_level_layout = QHBoxLayout()
        log_level_label = QLabel("Log Level:")
        log_level_label.setStyleSheet("color: #ffffff; font-size: 12px;")
        
        log_level_combo = QComboBox()
        log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        log_level_combo.setCurrentText("DEBUG")
        log_level_combo.setStyleSheet(self.get_combo_style())
        
        log_level_layout.addWidget(log_level_label)
        log_level_layout.addWidget(log_level_combo)
        log_level_layout.addStretch()
        
        # Log file path
        log_path_layout = QHBoxLayout()
        log_path_label = QLabel("Log File Path:")
        log_path_label.setStyleSheet("color: #ffffff; font-size: 12px;")
        
        log_path_input = QLineEdit("logs/app.log")
        log_path_input.setStyleSheet(self.get_input_style())
        
        log_path_layout.addWidget(log_path_label)
        log_path_layout.addWidget(log_path_input)
        
        logging_layout.addLayout(log_level_layout)
        logging_layout.addLayout(log_path_layout)
        
        layout.addWidget(download_group)
        layout.addWidget(sync_group)
        layout.addWidget(logging_group)
        
        return column
    
    def get_input_style(self):
        return """
            QLineEdit {
                background: #404040;
                border: 1px solid #606060;
                border-radius: 4px;
                padding: 8px;
                color: #ffffff;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 1px solid #1db954;
            }
        """
    
    def get_combo_style(self):
        return """
            QComboBox {
                background: #404040;
                border: 1px solid #606060;
                border-radius: 4px;
                padding: 8px;
                color: #ffffff;
                font-size: 11px;
                min-width: 100px;
            }
            QComboBox:focus {
                border: 1px solid #1db954;
            }
            QComboBox::drop-down {
                border: none;
            }
        """
    
    def get_spin_style(self):
        return """
            QSpinBox {
                background: #404040;
                border: 1px solid #606060;
                border-radius: 4px;
                padding: 8px;
                color: #ffffff;
                font-size: 11px;
                min-width: 80px;
            }
            QSpinBox:focus {
                border: 1px solid #1db954;
            }
        """
    
    def get_checkbox_style(self):
        return """
            QCheckBox {
                color: #ffffff;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid #b3b3b3;
                background: transparent;
            }
            QCheckBox::indicator:checked {
                background: #1db954;
                border: 2px solid #1db954;
            }
        """
    
    def get_test_button_style(self):
        return """
            QPushButton {
                background: transparent;
                border: 1px solid #1db954;
                border-radius: 15px;
                color: #1db954;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(29, 185, 84, 0.1);
            }
        """