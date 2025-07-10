from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                           QFrame, QPushButton, QProgressBar, QListWidget,
                           QListWidgetItem, QComboBox, QLineEdit, QScrollArea, QMessageBox,
                           QSplitter, QSizePolicy, QSpacerItem)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

class DownloadThread(QThread):
    download_completed = pyqtSignal(str)  # Download ID or success message
    download_failed = pyqtSignal(str)  # Error message
    download_progress = pyqtSignal(str)  # Progress message
    
    def __init__(self, soulseek_client, search_result):
        super().__init__()
        self.soulseek_client = soulseek_client
        self.search_result = search_result
        self._stop_requested = False
        
    def run(self):
        loop = None
        try:
            import asyncio
            self.download_progress.emit(f"Starting download: {self.search_result.filename}")
            
            # Create a completely fresh event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Perform download with proper error handling
            download_id = loop.run_until_complete(self._do_download())
            
            if not self._stop_requested:
                if download_id:
                    self.download_completed.emit(f"Download started: {download_id}")
                else:
                    self.download_failed.emit("Download failed to start")
            
        except Exception as e:
            if not self._stop_requested:
                self.download_failed.emit(str(e))
        finally:
            # Ensure proper cleanup
            if loop:
                try:
                    # Close any remaining tasks
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    
                    loop.close()
                except Exception as e:
                    print(f"Error cleaning up download event loop: {e}")
    
    async def _do_download(self):
        """Perform the actual download with proper async handling"""
        return await self.soulseek_client.download(
            self.search_result.username, 
            self.search_result.filename,
            self.search_result.size
        )
    
    def stop(self):
        """Stop the download gracefully"""
        self._stop_requested = True

class SessionInfoThread(QThread):
    session_info_completed = pyqtSignal(dict)  # Session info dict
    session_info_failed = pyqtSignal(str)  # Error message
    
    def __init__(self, soulseek_client):
        super().__init__()
        self.soulseek_client = soulseek_client
        self._stop_requested = False
        
    def run(self):
        loop = None
        try:
            import asyncio
            
            # Create a completely fresh event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Check if stop was requested before starting
            if self._stop_requested:
                return
            
            # Get session info
            session_info = loop.run_until_complete(self._get_session_info())
            
            # Only emit if not stopped
            if not self._stop_requested:
                self.session_info_completed.emit(session_info or {})
            
        except Exception as e:
            if not self._stop_requested:
                self.session_info_failed.emit(str(e))
        finally:
            # Ensure proper cleanup
            if loop:
                try:
                    # Close any remaining tasks
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    
                    loop.close()
                except Exception as e:
                    print(f"Error cleaning up session info event loop: {e}")
    
    async def _get_session_info(self):
        """Get the session information"""
        return await self.soulseek_client.get_session_info()
    
    def stop(self):
        """Stop the session info gathering gracefully"""
        self._stop_requested = True

class ExploreApiThread(QThread):
    exploration_completed = pyqtSignal(dict)  # API info dict
    exploration_failed = pyqtSignal(str)  # Error message
    
    def __init__(self, soulseek_client):
        super().__init__()
        self.soulseek_client = soulseek_client
        self._stop_requested = False
        
    def run(self):
        loop = None
        try:
            import asyncio
            
            # Create a completely fresh event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Check if stop was requested before starting
            if self._stop_requested:
                return
            
            # Explore the API
            api_info = loop.run_until_complete(self._explore_api())
            
            # Only emit if not stopped
            if not self._stop_requested:
                self.exploration_completed.emit(api_info)
            
        except Exception as e:
            if not self._stop_requested:
                self.exploration_failed.emit(str(e))
        finally:
            # Ensure proper cleanup
            if loop:
                try:
                    # Close any remaining tasks
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    
                    loop.close()
                except Exception as e:
                    print(f"Error cleaning up exploration event loop: {e}")
    
    async def _explore_api(self):
        """Perform the actual API exploration"""
        return await self.soulseek_client.explore_api_endpoints()
    
    def stop(self):
        """Stop the exploration gracefully"""
        self._stop_requested = True

class SearchThread(QThread):
    search_completed = pyqtSignal(list)  # List of search results
    search_failed = pyqtSignal(str)  # Error message
    search_progress = pyqtSignal(str)  # Progress message
    search_results_partial = pyqtSignal(list, int)  # Partial results, total count
    
    def __init__(self, soulseek_client, query):
        super().__init__()
        self.soulseek_client = soulseek_client
        self.query = query
        self._stop_requested = False
        self.all_results = []  # Track all results for final emit
        
    def progress_callback(self, new_results, total_count):
        """Callback function for progressive search results"""
        if not self._stop_requested:
            self.all_results.extend(new_results)
            self.search_results_partial.emit(new_results, total_count)
        
    def run(self):
        loop = None
        try:
            import asyncio
            self.search_progress.emit(f"Searching for: {self.query}")
            
            # Create a completely fresh event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Perform search with progressive callback
            results = loop.run_until_complete(self._do_search())
            
            if not self._stop_requested:
                # Emit final completion with all results
                self.search_completed.emit(self.all_results if self.all_results else results)
            
        except Exception as e:
            if not self._stop_requested:
                self.search_failed.emit(str(e))
        finally:
            # Ensure proper cleanup
            if loop:
                try:
                    # Close any remaining tasks
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    
                    loop.close()
                except Exception as e:
                    print(f"Error cleaning up event loop: {e}")
    
    async def _do_search(self):
        """Perform the actual search with progressive callback"""
        return await self.soulseek_client.search(self.query, progress_callback=self.progress_callback)
    
    def stop(self):
        """Stop the search gracefully"""
        self._stop_requested = True

class SearchResultItem(QFrame):
    download_requested = pyqtSignal(object)  # SearchResult object
    expansion_requested = pyqtSignal(object)  # Signal when this item wants to expand
    
    def __init__(self, search_result, parent=None):
        super().__init__(parent)
        self.search_result = search_result
        self.is_downloading = False
        self.is_expanded = False
        self.setup_ui()
    
    def setup_ui(self):
        # Dynamic height based on state (compact: 60px, expanded: 180px for better content fit)
        self.compact_height = 60
        self.expanded_height = 180  # Increased from 140px to fit content properly
        self.setFixedHeight(self.compact_height)
        
        # Ensure consistent sizing and layout behavior
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        # Enable mouse tracking for click detection
        self.setMouseTracking(True)
        
        self.setStyleSheet("""
            SearchResultItem {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(42, 42, 42, 0.9),
                    stop:1 rgba(32, 32, 32, 0.95));
                border-radius: 12px;
                border: 1px solid rgba(64, 64, 64, 0.4);
                margin: 4px 2px;
            }
            SearchResultItem:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(50, 50, 50, 0.95),
                    stop:1 rgba(40, 40, 40, 0.98));
                border: 1px solid rgba(29, 185, 84, 0.7);
                cursor: pointer;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)  # Tighter padding for compact view
        layout.setSpacing(12)
        
        # Left section: Music icon + filename
        left_section = QHBoxLayout()
        left_section.setSpacing(8)
        
        # Compact music icon
        music_icon = QLabel("🎵")
        music_icon.setFixedSize(32, 32)
        music_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        music_icon.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(29, 185, 84, 0.3),
                    stop:1 rgba(29, 185, 84, 0.1));
                border-radius: 16px;
                border: 1px solid rgba(29, 185, 84, 0.4);
                font-size: 14px;
            }
        """)
        
        # Content area that will change based on expanded state
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(3)  # Tighter spacing for better content density
        
        # Extract song info
        primary_info = self._extract_song_info()
        
        # Create both compact and expanded content but show only one
        self.create_persistent_content(primary_info)
        
        # Right section: Always-visible download button
        self.download_btn = QPushButton("⬇️")
        self.download_btn.setFixedSize(36, 36)
        self.download_btn.clicked.connect(self.request_download)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(29, 185, 84, 0.9),
                    stop:1 rgba(24, 156, 71, 0.9));
                border: none;
                border-radius: 18px;
                color: #000000;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(30, 215, 96, 1.0),
                    stop:1 rgba(25, 180, 80, 1.0));
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(24, 156, 71, 1.0),
                    stop:1 rgba(20, 130, 60, 1.0));
            }
        """)
        
        # Assemble the layout
        left_section.addWidget(music_icon)
        left_section.addWidget(self.content_widget, 1)
        
        layout.addLayout(left_section, 1)
        layout.addWidget(self.download_btn)
    
    def create_persistent_content(self, primary_info):
        """Create both compact and expanded content with visibility control"""
        # Title row (always visible) with character limit and ellipsis
        title_text = primary_info['title']
        if len(title_text) > 50:  # Character limit for long titles
            title_text = title_text[:47] + "..."
        
        self.title_label = QLabel(title_text)
        self.title_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))  # Reduced from 13px to 11px
        self.title_label.setStyleSheet("color: #ffffff;")
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        # Ensure text doesn't overflow the label
        self.title_label.setWordWrap(False)
        self.title_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        
        # Expand indicator
        self.expand_indicator = QLabel("⏵")
        self.expand_indicator.setFixedSize(16, 16)
        self.expand_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.expand_indicator.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 12px;")
        
        # Quality badge (only visible when expanded)
        self.quality_badge = self._create_compact_quality_badge()
        self.quality_badge.hide()  # Initially hidden
        
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.addWidget(self.title_label)
        title_row.addWidget(self.quality_badge)
        title_row.addWidget(self.expand_indicator)
        
        # Expanded content (initially hidden)
        self.expanded_content = QWidget()
        expanded_layout = QVBoxLayout(self.expanded_content)
        expanded_layout.setContentsMargins(0, 0, 0, 0)
        expanded_layout.setSpacing(2)  # Very tight spacing for dense layout
        
        # Artist info
        self.artist_info = QLabel(primary_info['artist'])
        self.artist_info.setFont(QFont("Arial", 10, QFont.Weight.Normal))  # Slightly smaller font
        self.artist_info.setStyleSheet("color: rgba(179, 179, 179, 0.9);")
        
        # File details
        details = []
        size_mb = self.search_result.size // (1024*1024)
        details.append(f"{size_mb}MB")
        
        if self.search_result.duration:
            duration_mins = self.search_result.duration // 60
            duration_secs = self.search_result.duration % 60
            details.append(f"{duration_mins}:{duration_secs:02d}")
        
        self.file_details = QLabel(" • ".join(details))
        self.file_details.setFont(QFont("Arial", 9))  # Smaller font for compactness
        self.file_details.setStyleSheet("color: rgba(136, 136, 136, 0.8);")
        
        # User info and quality score in one compact row
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(8)
        
        self.user_info = QLabel(f"👤 {self.search_result.username}")
        self.user_info.setFont(QFont("Arial", 9, QFont.Weight.Medium))  # Smaller font
        self.user_info.setStyleSheet("color: rgba(29, 185, 84, 0.8);")
        
        self.speed_indicator = self._create_compact_speed_indicator()
        
        self.quality_score = QLabel(f"★{self.search_result.quality_score:.1f}")
        self.quality_score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.quality_score.setFont(QFont("Arial", 8, QFont.Weight.Bold))  # Smaller font
        self.quality_score.setFixedSize(32, 16)  # Smaller size
        
        if self.search_result.quality_score >= 0.9:
            self.quality_score.setStyleSheet("color: #1db954; background: rgba(29, 185, 84, 0.15); border-radius: 8px;")
        elif self.search_result.quality_score >= 0.7:
            self.quality_score.setStyleSheet("color: #ffa500; background: rgba(255, 165, 0, 0.15); border-radius: 8px;")
        else:
            self.quality_score.setStyleSheet("color: #e22134; background: rgba(226, 33, 52, 0.15); border-radius: 8px;")
        
        bottom_row.addWidget(self.user_info)
        bottom_row.addWidget(self.speed_indicator)
        bottom_row.addStretch()
        bottom_row.addWidget(self.quality_score)
        
        # Add all expanded content
        expanded_layout.addWidget(self.artist_info)
        expanded_layout.addWidget(self.file_details)
        expanded_layout.addLayout(bottom_row)
        
        # Initially hide expanded content
        self.expanded_content.hide()
        
        # Add to main layout
        self.content_layout.addLayout(title_row)
        self.content_layout.addWidget(self.expanded_content)
    
    def update_expanded_state(self):
        """Update UI based on expanded state without recreating widgets"""
        if self.is_expanded:
            self.expand_indicator.setText("⏷")
            self.quality_badge.show()
            self.expanded_content.show()
        else:
            self.expand_indicator.setText("⏵")
            self.quality_badge.hide()
            self.expanded_content.hide()
    
    def mousePressEvent(self, event):
        """Handle mouse clicks to toggle expand/collapse"""
        # Only respond to left clicks and avoid clicks on the download button
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if click is on download button (more precise detection)
            button_rect = self.download_btn.geometry()
            # Add some padding to the button area to be more forgiving
            button_rect.adjust(-5, -5, 5, 5)
            if not button_rect.contains(event.pos()):
                # Emit signal to parent to handle accordion behavior
                self.expansion_requested.emit(self)
        super().mousePressEvent(event)
    
    def set_expanded(self, expanded, animate=True):
        """Set expanded state externally (called by parent for accordion behavior)"""
        if self.is_expanded == expanded:
            return  # No change needed
        
        self.is_expanded = expanded
        
        if animate:
            self._animate_to_state()
        else:
            # Immediate state change without animation
            if self.is_expanded:
                self.setFixedHeight(self.expanded_height)
            else:
                self.setFixedHeight(self.compact_height)
            self.update_expanded_state()
    
    def toggle_expanded(self):
        """Toggle between compact and expanded states with animation"""
        self.set_expanded(not self.is_expanded, animate=True)
    
    def _animate_to_state(self):
        """Animate to the current expanded state"""
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
        
        # Start height animation first
        self.animation = QPropertyAnimation(self, b"minimumHeight")
        self.animation.setDuration(200)  # Slightly faster animation for better responsiveness
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        if self.is_expanded:
            # Expand animation
            self.animation.setStartValue(self.compact_height)
            self.animation.setEndValue(self.expanded_height)
            # Show content immediately for expand (feels more responsive)
            self.update_expanded_state()
        else:
            # Collapse animation
            self.animation.setStartValue(self.expanded_height)
            self.animation.setEndValue(self.compact_height)
            # Hide content immediately for collapse (cleaner look)
            self.update_expanded_state()
        
        # Update fixed height when animation completes
        self.animation.finished.connect(self._finalize_height)
        self.animation.start()
    
    def _finalize_height(self):
        """Set final height after animation completes"""
        if self.is_expanded:
            self.setFixedHeight(self.expanded_height)
        else:
            self.setFixedHeight(self.compact_height)
        
        # Force parent layout update to ensure proper spacing
        if self.parent():
            self.parent().updateGeometry()
    
    def sizeHint(self):
        """Provide consistent size hint for layout calculations"""
        if self.is_expanded:
            return self.size().expandedTo(self.minimumSize()).boundedTo(self.maximumSize())
        else:
            return self.size().expandedTo(self.minimumSize()).boundedTo(self.maximumSize())
    
    def _extract_song_info(self):
        """Extract song title and artist from filename"""
        filename = self.search_result.filename
        
        # Remove file extension
        name_without_ext = filename.rsplit('.', 1)[0]
        
        # Common patterns for artist - title separation
        separators = [' - ', ' – ', ' — ', '_-_', ' | ']
        
        for sep in separators:
            if sep in name_without_ext:
                parts = name_without_ext.split(sep, 1)
                return {
                    'title': parts[1].strip(),
                    'artist': parts[0].strip()
                }
        
        # If no separator found, use filename as title
        return {
            'title': name_without_ext,
            'artist': 'Unknown Artist'
        }
    
    def _create_compact_quality_badge(self):
        """Create a compact quality indicator badge"""
        quality = self.search_result.quality.upper()
        bitrate = self.search_result.bitrate
        
        if quality == 'FLAC':
            badge_text = "FLAC"
            badge_color = "#1db954"
        elif bitrate and bitrate >= 320:
            badge_text = f"{bitrate}k"
            badge_color = "#1db954"
        elif bitrate and bitrate >= 256:
            badge_text = f"{bitrate}k"
            badge_color = "#ffa500"
        elif bitrate and bitrate >= 192:
            badge_text = f"{bitrate}k"
            badge_color = "#ffaa00"
        else:
            badge_text = quality[:3]  # Truncate for compact display
            badge_color = "#e22134"
        
        badge = QLabel(badge_text)
        badge.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(40, 16)
        badge.setStyleSheet(f"""
            QLabel {{
                background: {badge_color};
                color: #000000;
                border-radius: 8px;
                padding: 1px 4px;
            }}
        """)
        
        return badge
    
    def _create_compact_speed_indicator(self):
        """Create compact upload speed indicator"""
        speed = self.search_result.upload_speed
        slots = self.search_result.free_upload_slots
        
        if slots > 0 and speed > 100:
            indicator_color = "#1db954"
            speed_text = "🚀"
        elif slots > 0:
            indicator_color = "#ffa500"
            speed_text = "⚡"
        else:
            indicator_color = "#e22134"
            speed_text = "⏳"
        
        indicator = QLabel(speed_text)
        indicator.setFont(QFont("Arial", 10))
        indicator.setStyleSheet(f"color: {indicator_color};")
        indicator.setFixedSize(16, 16)
        
        return indicator
    
    def _create_quality_badge(self):
        """Create a quality indicator badge (legacy - kept for compatibility)"""
        return self._create_compact_quality_badge()
    
    def _create_speed_indicator(self):
        """Create upload speed indicator (legacy - kept for compatibility)"""
        return self._create_compact_speed_indicator()
    
    def request_download(self):
        if not self.is_downloading:
            self.is_downloading = True
            self.download_btn.setText("⏳")
            self.download_btn.setEnabled(False)
            self.download_requested.emit(self.search_result)
    
    def reset_download_state(self):
        """Reset the download button state"""
        self.is_downloading = False
        self.download_btn.setText("⬇️")
        self.download_btn.setEnabled(True)

class DownloadItem(QFrame):
    def __init__(self, title: str, artist: str, status: str, progress: int = 0, 
                 file_size: int = 0, download_speed: int = 0, file_path: str = "", parent=None):
        super().__init__(parent)
        self.title = title
        self.artist = artist
        self.status = status
        self.progress = progress
        self.file_size = file_size
        self.download_speed = download_speed
        self.file_path = file_path
        self.setup_ui()
    
    def setup_ui(self):
        self.setFixedHeight(90)  # Consistent with search results
        self.setStyleSheet("""
            DownloadItem {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(42, 42, 42, 0.9),
                    stop:1 rgba(32, 32, 32, 0.95));
                border-radius: 12px;
                border: 1px solid rgba(64, 64, 64, 0.4);
                margin: 6px 4px;
            }
            DownloadItem:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(50, 50, 50, 0.95),
                    stop:1 rgba(40, 40, 40, 0.98));
                border: 1px solid rgba(29, 185, 84, 0.7);
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)  # Consistent with search items
        layout.setSpacing(16)  # Professional spacing
        
        # Status icon
        status_icon = QLabel()
        status_icon.setFixedSize(32, 32)
        status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if self.status == "downloading":
            status_icon.setText("📥")
            status_icon.setStyleSheet("""
                QLabel {
                    color: #1db954;
                    font-size: 18px;
                    background: rgba(29, 185, 84, 0.1);
                    border-radius: 16px;
                }
            """)
        elif self.status == "completed":
            status_icon.setText("✅")
            status_icon.setStyleSheet("""
                QLabel {
                    color: #1db954;
                    font-size: 18px;
                    background: rgba(29, 185, 84, 0.1);
                    border-radius: 16px;
                }
            """)
        elif self.status == "failed":
            status_icon.setText("❌")
            status_icon.setStyleSheet("""
                QLabel {
                    color: #e22134;
                    font-size: 18px;
                    background: rgba(226, 33, 52, 0.1);
                    border-radius: 16px;
                }
            """)
        else:
            status_icon.setText("⏳")
            status_icon.setStyleSheet("""
                QLabel {
                    color: #ffa500;
                    font-size: 18px;
                    background: rgba(255, 165, 0, 0.1);
                    border-radius: 16px;
                }
            """)
        
        # Content
        content_layout = QVBoxLayout()
        content_layout.setSpacing(5)
        
        # Title and artist
        title_label = QLabel(self.title)
        title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #ffffff;")
        
        artist_label = QLabel(f"by {self.artist}")
        artist_label.setFont(QFont("Arial", 10))
        artist_label.setStyleSheet("color: #b3b3b3;")
        
        content_layout.addWidget(title_label)
        content_layout.addWidget(artist_label)
        
        # Progress section
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(5)
        
        # Progress bar
        progress_bar = QProgressBar()
        progress_bar.setFixedHeight(6)
        progress_bar.setValue(self.progress)
        progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 3px;
                background: #404040;
            }
            QProgressBar::chunk {
                background: #1db954;
                border-radius: 3px;
            }
        """)
        
        # Status text
        status_text = f"{self.status.title()}"
        if self.status == "downloading":
            status_text += f" - {self.progress}%"
        
        status_label = QLabel(status_text)
        status_label.setFont(QFont("Arial", 9))
        status_label.setStyleSheet("color: #b3b3b3;")
        
        progress_layout.addWidget(progress_bar)
        progress_layout.addWidget(status_label)
        
        # Action buttons section
        actions_layout = QVBoxLayout()
        actions_layout.setSpacing(4)
        
        # Primary action button
        action_btn = QPushButton()
        action_btn.setFixedSize(80, 28)
        
        if self.status == "downloading":
            action_btn.setText("Cancel")
            action_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: 1px solid #e22134;
                    border-radius: 14px;
                    color: #e22134;
                    font-size: 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #e22134;
                    color: #ffffff;
                }
            """)
        elif self.status == "failed":
            action_btn.setText("Retry")
            action_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: 1px solid #1db954;
                    border-radius: 14px;
                    color: #1db954;
                    font-size: 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #1db954;
                    color: #000000;
                }
            """)
        else:
            action_btn.setText("Details")
            action_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: 1px solid #b3b3b3;
                    border-radius: 14px;
                    color: #b3b3b3;
                    font-size: 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #b3b3b3;
                    color: #000000;
                }
            """)
        
        # Open Location button (for completed downloads)
        location_btn = QPushButton("📂 Open")
        location_btn.setFixedSize(80, 28)
        location_btn.clicked.connect(self.open_download_location)
        location_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid rgba(29, 185, 84, 0.6);
                border-radius: 14px;
                color: rgba(29, 185, 84, 0.9);
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(29, 185, 84, 0.1);
                border: 1px solid rgba(29, 185, 84, 0.8);
            }
        """)
        
        actions_layout.addWidget(action_btn)
        if self.status == "completed" and self.file_path:
            actions_layout.addWidget(location_btn)
        
        layout.addWidget(status_icon)
        layout.addLayout(content_layout)
        layout.addStretch()
        layout.addLayout(progress_layout)
        layout.addLayout(actions_layout)
    
    def open_download_location(self):
        """Open the download location in file explorer"""
        import os
        import platform
        from pathlib import Path
        
        if not self.file_path:
            return
            
        try:
            file_path = Path(self.file_path)
            if file_path.exists():
                # Open the folder containing the file
                folder_path = file_path.parent
                
                system = platform.system()
                if system == "Windows":
                    os.startfile(str(folder_path))
                elif system == "Darwin":  # macOS
                    os.system(f'open "{folder_path}"')
                else:  # Linux
                    os.system(f'xdg-open "{folder_path}"')
            else:
                # If file doesn't exist, try to open the download directory from config
                from config.settings import config_manager
                download_path = config_manager.get('soulseek.download_path', './downloads')
                
                system = platform.system()
                if system == "Windows":
                    os.startfile(download_path)
                elif system == "Darwin":  # macOS
                    os.system(f'open "{download_path}"')
                else:  # Linux
                    os.system(f'xdg-open "{download_path}"')
                    
        except Exception as e:
            print(f"Error opening download location: {e}")
    
    def update_status(self, status: str, progress: int = None, download_speed: int = None, file_path: str = None):
        """Update download item status and refresh UI"""
        self.status = status
        if progress is not None:
            self.progress = progress
        if download_speed is not None:
            self.download_speed = download_speed
        if file_path:
            self.file_path = file_path
            
        # Refresh the UI by recreating it
        # Clear current layout
        while self.layout().count():
            child = self.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Recreate UI with updated values
        self.setup_ui()

class DownloadQueue(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet("""
            DownloadQueue {
                background: #282828;
                border-radius: 8px;
                border: 1px solid #404040;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 16)  # Reduced top padding
        layout.setSpacing(8)  # Tighter spacing for more compact layout
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("Download Queue")
        title_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.95);
            font-weight: 600;
            padding: 0;
        """)
        
        queue_count = QLabel("Empty")
        queue_count.setFont(QFont("Segoe UI", 10))
        queue_count.setStyleSheet("""
            color: rgba(255, 255, 255, 0.6);
            padding: 0;
        """)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(queue_count)
        
        # Queue list
        queue_scroll = QScrollArea()
        queue_scroll.setWidgetResizable(True)
        queue_scroll.setFixedHeight(300)
        queue_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #404040;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #1db954;
                border-radius: 4px;
            }
        """)
        
        queue_widget = QWidget()
        queue_layout = QVBoxLayout(queue_widget)
        queue_layout.setSpacing(8)
        
        # Dynamic download items - initially empty
        self.queue_layout = queue_layout
        self.queue_count_label = queue_count
        self.download_items = []
        
        # Add initial message when queue is empty
        self.empty_message = QLabel("No downloads yet. Start downloading music to see them here!")
        self.empty_message.setFont(QFont("Arial", 11))
        self.empty_message.setStyleSheet("color: rgba(255, 255, 255, 0.5); padding: 20px; text-align: center;")
        self.empty_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        queue_layout.addWidget(self.empty_message)
        
        queue_layout.addStretch()
        queue_scroll.setWidget(queue_widget)
        
        layout.addLayout(header_layout)
        layout.addWidget(queue_scroll)
    
    def add_download_item(self, title: str, artist: str, status: str = "queued", 
                         progress: int = 0, file_size: int = 0, download_speed: int = 0, file_path: str = ""):
        """Add a new download item to the queue"""
        # Hide empty message if this is the first item
        if len(self.download_items) == 0:
            self.empty_message.hide()
        
        # Create new download item
        item = DownloadItem(title, artist, status, progress, file_size, download_speed, file_path)
        self.download_items.append(item)
        
        # Insert before the stretch (which is always last)
        insert_index = self.queue_layout.count() - 1
        self.queue_layout.insertWidget(insert_index, item)
        
        # Update count
        self.update_queue_count()
        
        return item
    
    def update_queue_count(self):
        """Update the queue count label"""
        count = len(self.download_items)
        if count == 0:
            self.queue_count_label.setText("Empty")
            if not self.empty_message.isHidden():
                self.empty_message.show()
        else:
            self.queue_count_label.setText(f"{count} item{'s' if count != 1 else ''}")
    
    def remove_download_item(self, item):
        """Remove a download item from the queue"""
        if item in self.download_items:
            self.download_items.remove(item)
            self.queue_layout.removeWidget(item)
            item.deleteLater()
            self.update_queue_count()
    
    def clear_completed_downloads(self):
        """Remove all completed download items"""
        items_to_remove = []
        for item in self.download_items:
            if item.status == "completed":
                items_to_remove.append(item)
        
        for item in items_to_remove:
            self.remove_download_item(item)

class DownloadsPage(QWidget):
    def __init__(self, soulseek_client=None, parent=None):
        super().__init__(parent)
        self.soulseek_client = soulseek_client
        self.search_thread = None
        self.explore_thread = None  # Track API exploration thread
        self.session_thread = None  # Track session info thread
        self.download_threads = []  # Track active download threads
        self.search_results = []
        self.download_items = []  # Track download items for the queue
        self.displayed_results = 0  # Track how many results are currently displayed
        self.results_per_page = 15  # Show 15 results at a time
        self.is_loading_more = False  # Prevent multiple simultaneous loads
        self.currently_expanded_item = None  # Track which item is currently expanded
        
        # Download status polling timer
        self.download_status_timer = QTimer()
        self.download_status_timer.timeout.connect(self.update_download_status)
        self.download_status_timer.start(2000)  # Poll every 2 seconds
        
        
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet("""
            DownloadsPage {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(25, 20, 20, 1.0),
                    stop:1 rgba(15, 15, 15, 1.0));
            }
        """)
        
        main_layout = QVBoxLayout(self)
        # Responsive margins that adapt to window size  
        main_layout.setContentsMargins(16, 12, 16, 16)  # Reduced for tighter responsive feel
        main_layout.setSpacing(12)  # Consistent 12px spacing
        
        # Elegant Header
        header = self.create_elegant_header()
        main_layout.addWidget(header)
        
        # Main Content Area with responsive splitter
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.setChildrenCollapsible(False)  # Prevent panels from collapsing completely
        
        # LEFT: Search & Results section
        search_and_results = self.create_search_and_results_section()
        search_and_results.setMinimumWidth(400)  # Minimum width for usability
        content_splitter.addWidget(search_and_results)
        
        # RIGHT: Controls Panel
        controls_panel = self.create_collapsible_controls_panel()
        controls_panel.setMinimumWidth(280)  # Minimum width for controls
        controls_panel.setMaximumWidth(400)  # Maximum width to prevent overgrowth
        content_splitter.addWidget(controls_panel)
        
        # Set initial splitter proportions (roughly 70/30)
        content_splitter.setSizes([700, 300])
        content_splitter.setStretchFactor(0, 1)  # Search results gets priority for extra space
        content_splitter.setStretchFactor(1, 0)  # Controls panel stays fixed width when possible
        
        main_layout.addWidget(content_splitter)
        
        # Optional: Compact status bar at bottom
        status_bar = self.create_compact_status_bar()
        main_layout.addWidget(status_bar)
    
    def create_elegant_header(self):
        """Create an elegant, minimal header"""
        header = QFrame()
        header.setMinimumHeight(80)  # Minimum height, can grow if needed
        header.setMaximumHeight(120)  # Maximum to prevent overgrowth
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        header.setStyleSheet("""
            QFrame {
                background: transparent;
                border: none;
            }
        """)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 12, 16, 12)  # Responsive padding consistent with main layout
        layout.setSpacing(12)  # Consistent spacing
        
        # Icon and Title
        title_section = QVBoxLayout()
        title_section.setSpacing(4)
        
        title_label = QLabel("🎵 Music Downloads")
        title_label.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        title_label.setStyleSheet("""
            color: #ffffff;
            font-weight: 700;
            letter-spacing: 1px;
        """)
        
        subtitle_label = QLabel("Search, discover, and download high-quality music")
        subtitle_label.setFont(QFont("Segoe UI", 13))
        subtitle_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.85);
            font-weight: 300;
            letter-spacing: 0.5px;
            margin-top: 4px;
        """)
        
        title_section.addWidget(title_label)
        title_section.addWidget(subtitle_label)
        
        layout.addLayout(title_section)
        layout.addStretch()
        
        return header
    
    def create_search_and_results_section(self):
        """Create the main search and results area - the star of the show"""
        section = QFrame()
        section.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(40, 40, 40, 0.4),
                    stop:1 rgba(30, 30, 30, 0.6));
                border-radius: 16px;
                border: 1px solid rgba(64, 64, 64, 0.3);
            }
        """)
        
        layout = QVBoxLayout(section)
        layout.setContentsMargins(16, 12, 16, 12)  # Responsive spacing consistent with main layout
        layout.setSpacing(12)  # Consistent 12px spacing
        
        # Elegant Search Bar
        search_container = self.create_elegant_search_bar()
        layout.addWidget(search_container)
        
        # Search Status with better visual feedback
        self.search_status = QLabel("Ready to search • Enter artist, song, or album name")
        self.search_status.setFont(QFont("Arial", 11))
        self.search_status.setStyleSheet("""
            color: rgba(255, 255, 255, 0.7);
            padding: 10px 18px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 rgba(29, 185, 84, 0.12),
                stop:1 rgba(29, 185, 84, 0.08));
            border-radius: 10px;
            border: 1px solid rgba(29, 185, 84, 0.25);
        """)
        layout.addWidget(self.search_status)
        
        # Search Results - The main attraction
        results_container = QFrame()
        results_container.setStyleSheet("""
            QFrame {
                background: rgba(20, 20, 20, 0.3);
                border-radius: 12px;
                border: 1px solid rgba(64, 64, 64, 0.2);
            }
        """)
        
        results_layout = QVBoxLayout(results_container)
        results_layout.setContentsMargins(12, 8, 12, 12)  # Tighter responsive spacing
        results_layout.setSpacing(8)  # Consistent small spacing for tight layout
        
        # Results header
        results_header = QLabel("Search Results")
        results_header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        results_header.setStyleSheet("""
            color: rgba(255, 255, 255, 0.95);
            font-weight: 600;
            padding: 4px 8px;
        """)
        results_layout.addWidget(results_header)
        
        # Scrollable results area - this gets ALL remaining space
        self.search_results_scroll = QScrollArea()
        self.search_results_scroll.setWidgetResizable(True)
        self.search_results_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.search_results_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.search_results_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
                border-radius: 8px;
            }
            QScrollBar:vertical {
                background: rgba(64, 64, 64, 0.3);
                width: 8px;
                border-radius: 4px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(29, 185, 84, 0.8),
                    stop:1 rgba(29, 185, 84, 0.6));
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(29, 185, 84, 1.0);
            }
        """)
        
        self.search_results_widget = QWidget()
        self.search_results_layout = QVBoxLayout(self.search_results_widget)
        self.search_results_layout.setSpacing(8)
        self.search_results_layout.setContentsMargins(4, 4, 4, 4)
        self.search_results_layout.addStretch()
        self.search_results_scroll.setWidget(self.search_results_widget)
        
        # Connect scroll detection for automatic loading
        scroll_bar = self.search_results_scroll.verticalScrollBar()
        scroll_bar.valueChanged.connect(self.on_scroll_changed)
        
        results_layout.addWidget(self.search_results_scroll)
        layout.addWidget(results_container, 1)  # This takes all remaining space
        
        return section
    
    def create_elegant_search_bar(self):
        """Create a beautiful, modern search bar"""
        container = QFrame()
        container.setFixedHeight(70)
        container.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(50, 50, 50, 0.8),
                    stop:1 rgba(40, 40, 40, 0.9));
                border-radius: 12px;
                border: 1px solid rgba(29, 185, 84, 0.3);
            }
        """)
        
        layout = QHBoxLayout(container)
        layout.setContentsMargins(16, 12, 16, 12)  # Consistent responsive spacing
        layout.setSpacing(12)  # Consistent spacing throughout
        
        # Search input with enhanced styling
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for music... (e.g., 'Virtual Mage', 'Queen Bohemian Rhapsody')")
        self.search_input.setFixedHeight(40)
        self.search_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)  # Responsive width
        self.search_input.returnPressed.connect(self.perform_search)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: rgba(60, 60, 60, 0.7);
                border: 2px solid rgba(100, 100, 100, 0.3);
                border-radius: 20px;
                padding: 0 20px;
                color: #ffffff;
                font-size: 14px;
                font-weight: 500;
            }
            QLineEdit:focus {
                border: 2px solid rgba(29, 185, 84, 0.8);
                background: rgba(70, 70, 70, 0.9);
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.5);
            }
        """)
        
        # Enhanced search button
        self.search_btn = QPushButton("🔍 Search")
        self.search_btn.setFixedSize(120, 40)
        self.search_btn.clicked.connect(self.perform_search)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(29, 185, 84, 1.0),
                    stop:1 rgba(24, 156, 71, 1.0));
                border: none;
                border-radius: 20px;
                color: #000000;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(30, 215, 96, 1.0),
                    stop:1 rgba(25, 180, 80, 1.0));
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(24, 156, 71, 1.0),
                    stop:1 rgba(20, 130, 60, 1.0));
            }
            QPushButton:disabled {
                background: rgba(100, 100, 100, 0.3);
                color: rgba(255, 255, 255, 0.3);
            }
        """)
        
        layout.addWidget(self.search_input)
        layout.addWidget(self.search_btn)
        
        return container
    
    def create_collapsible_controls_panel(self):
        """Create a compact, elegant controls panel"""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(35, 35, 35, 0.8),
                    stop:1 rgba(25, 25, 25, 0.9));
                border-radius: 16px;
                border: 1px solid rgba(64, 64, 64, 0.3);
            }
        """)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)  # Consistent responsive spacing
        layout.setSpacing(12)  # Consistent spacing throughout
        
        # Panel header
        header = QLabel("Download Manager")
        header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: rgba(255, 255, 255, 0.9); padding: 8px 0;")
        layout.addWidget(header)
        
        # Quick stats
        stats_frame = QFrame()
        stats_frame.setStyleSheet("""
            QFrame {
                background: rgba(45, 45, 45, 0.6);
                border-radius: 8px;
                border: 1px solid rgba(64, 64, 64, 0.4);
            }
        """)
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setContentsMargins(12, 10, 12, 10)
        stats_layout.setSpacing(6)
        
        active_downloads = QLabel("• Active Downloads: 0")
        active_downloads.setFont(QFont("Arial", 10))
        active_downloads.setStyleSheet("color: rgba(255, 255, 255, 0.8);")
        
        queue_length = QLabel("• Queue Length: 0")
        queue_length.setFont(QFont("Arial", 10))
        queue_length.setStyleSheet("color: rgba(255, 255, 255, 0.8);")
        
        stats_layout.addWidget(active_downloads)
        stats_layout.addWidget(queue_length)
        layout.addWidget(stats_frame)
        
        # Control buttons
        controls_frame = QFrame()
        controls_frame.setStyleSheet("""
            QFrame {
                background: rgba(40, 40, 40, 0.5);
                border-radius: 8px;
                border: 1px solid rgba(64, 64, 64, 0.3);
            }
        """)
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setContentsMargins(12, 12, 12, 12)
        controls_layout.setSpacing(8)
        
        pause_btn = QPushButton("⏸️ Pause All")
        pause_btn.setFixedHeight(32)
        pause_btn.setStyleSheet(self._get_control_button_style("#ffa500"))
        
        clear_btn = QPushButton("🗑️ Clear Completed")
        clear_btn.setFixedHeight(32)
        clear_btn.clicked.connect(self.clear_completed_downloads)
        clear_btn.setStyleSheet(self._get_control_button_style("#e22134"))
        
        controls_layout.addWidget(pause_btn)
        controls_layout.addWidget(clear_btn)
        layout.addWidget(controls_frame)
        
        # Download Queue Section
        self.download_queue = DownloadQueue()
        layout.addWidget(self.download_queue)
        
        # Add stretch to push everything to top
        layout.addStretch()
        
        return panel
    
    def create_compact_status_bar(self):
        """Create a minimal status bar"""
        status_bar = QFrame()
        status_bar.setFixedHeight(40)
        status_bar.setStyleSheet("""
            QFrame {
                background: rgba(20, 20, 20, 0.8);
                border-radius: 8px;
                border: 1px solid rgba(64, 64, 64, 0.2);
            }
        """)
        
        layout = QHBoxLayout(status_bar)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)
        
        connection_status = QLabel("🟢 slskd Connected")
        connection_status.setFont(QFont("Arial", 10))
        connection_status.setStyleSheet("color: rgba(29, 185, 84, 0.9);")
        
        layout.addWidget(connection_status)
        layout.addStretch()
        
        download_path_info = QLabel(f"📁 Downloads: {self.soulseek_client.download_path if self.soulseek_client else './downloads'}")
        download_path_info.setFont(QFont("Arial", 9))
        download_path_info.setStyleSheet("color: rgba(255, 255, 255, 0.6);")
        layout.addWidget(download_path_info)
        
        return status_bar
    
    def _get_control_button_style(self, color):
        """Get consistent button styling"""
        return f"""
            QPushButton {{
                background: rgba{tuple(int(color[i:i+2], 16) for i in (1, 3, 5)) + (51,)};
                border: 1px solid {color};
                border-radius: 16px;
                color: {color};
                font-size: 11px;
                font-weight: bold;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background: rgba{tuple(int(color[i:i+2], 16) for i in (1, 3, 5)) + (77,)};
            }}
        """
    
    def create_search_section(self):
        section = QFrame()
        section.setFixedHeight(350)
        section.setStyleSheet("""
            QFrame {
                background: #282828;
                border-radius: 8px;
                border: 1px solid #404040;
            }
        """)
        
        layout = QVBoxLayout(section)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Search header
        search_header = QLabel("Search & Download")
        search_header.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        search_header.setStyleSheet("color: #ffffff;")
        
        # Search input and button
        search_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for music (e.g., 'Artist - Song Title')")
        self.search_input.setFixedHeight(40)
        self.search_input.returnPressed.connect(self.perform_search)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: #404040;
                border: 1px solid #606060;
                border-radius: 20px;
                padding: 0 15px;
                color: #ffffff;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #1db954;
            }
        """)
        
        self.search_btn = QPushButton("🔍 Search")
        self.search_btn.setFixedSize(100, 40)
        self.search_btn.clicked.connect(self.perform_search)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background: #1db954;
                border: none;
                border-radius: 20px;
                color: #000000;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #1ed760;
            }
            QPushButton:disabled {
                background: #404040;
                color: #666666;
            }
        """)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_btn)
        
        # Search status
        self.search_status = QLabel("Enter a search term and click Search")
        self.search_status.setFont(QFont("Arial", 10))
        self.search_status.setStyleSheet("color: #b3b3b3;")
        
        # Search results
        self.search_results_scroll = QScrollArea()
        self.search_results_scroll.setWidgetResizable(True)
        self.search_results_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #404040;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #1db954;
                border-radius: 4px;
            }
        """)
        
        self.search_results_widget = QWidget()
        self.search_results_layout = QVBoxLayout(self.search_results_widget)
        self.search_results_layout.setSpacing(5)
        
        # Just add stretch - no load more button needed with auto-scroll
        self.search_results_layout.addStretch()
        self.search_results_scroll.setWidget(self.search_results_widget)
        
        layout.addWidget(search_header)
        layout.addLayout(search_layout)
        layout.addWidget(self.search_status)
        layout.addWidget(self.search_results_scroll)
        
        return section
    
    def perform_search(self):
        query = self.search_input.text().strip()
        if not query:
            self.update_search_status("⚠️ Please enter a search term", "#ffa500")
            return
        
        if not self.soulseek_client:
            self.update_search_status("❌ Soulseek client not available", "#e22134")
            return
        
        # Stop any existing search
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.stop()
            self.search_thread.wait(1000)  # Wait up to 1 second
            if self.search_thread.isRunning():
                self.search_thread.terminate()
        
        # Clear previous results and reset state
        self.clear_search_results()
        self.displayed_results = 0
        self.is_loading_more = False
        self.currently_expanded_item = None  # Reset expanded state
        
        # Enhanced searching state with animation
        self.search_btn.setText("🔍 Searching...")
        self.search_btn.setEnabled(False)
        self.update_search_status(f"🔍 Searching for '{query}'... Results will appear as they are found", "#1db954")
        
        # Start new search thread
        self.search_thread = SearchThread(self.soulseek_client, query)
        self.search_thread.search_completed.connect(self.on_search_completed)
        self.search_thread.search_failed.connect(self.on_search_failed)
        self.search_thread.search_progress.connect(self.on_search_progress)
        self.search_thread.search_results_partial.connect(self.on_search_results_partial)
        self.search_thread.finished.connect(self.on_search_thread_finished)
        self.search_thread.start()
    
    def update_search_status(self, message, color="#ffffff"):
        """Update search status with enhanced styling"""
        self.search_status.setText(message)
        
        if color == "#1db954":  # Success/searching
            bg_color = "rgba(29, 185, 84, 0.15)"
            border_color = "rgba(29, 185, 84, 0.3)"
        elif color == "#ffa500":  # Warning
            bg_color = "rgba(255, 165, 0, 0.15)"
            border_color = "rgba(255, 165, 0, 0.3)"
        elif color == "#e22134":  # Error
            bg_color = "rgba(226, 33, 52, 0.15)"
            border_color = "rgba(226, 33, 52, 0.3)"
        else:  # Default
            bg_color = "rgba(100, 100, 100, 0.1)"
            border_color = "rgba(100, 100, 100, 0.2)"
        
        self.search_status.setStyleSheet(f"""
            color: {color};
            padding: 12px 20px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {bg_color},
                stop:1 rgba(255, 255, 255, 0.02));
            border-radius: 12px;
            border: 1px solid {border_color};
        """)
    
    def on_search_thread_finished(self):
        """Clean up when search thread finishes"""
        if self.search_thread:
            self.search_thread.deleteLater()
            self.search_thread = None
    
    def clear_search_results(self):
        # Remove all result items except the stretch
        for i in reversed(range(self.search_results_layout.count())):
            item = self.search_results_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
            elif item.spacerItem():
                continue  # Keep the stretch spacer
            else:
                self.search_results_layout.removeItem(item)
    
    def on_search_results_partial(self, new_results, total_count):
        """Handle progressive search results as they come in"""
        # Sort new results by quality score and add to master list
        new_results.sort(key=lambda x: x.quality_score, reverse=True)
        
        # Add to master search results list (don't display all immediately)
        if not hasattr(self, '_temp_search_results'):
            self._temp_search_results = []
        
        self._temp_search_results.extend(new_results)
        
        # Only display up to the current page limit 
        remaining_slots = self.results_per_page - self.displayed_results
        if remaining_slots > 0:
            results_to_show = new_results[:remaining_slots]
            
            # Temporarily disable layout updates for smoother batch loading
            self.search_results_widget.setUpdatesEnabled(False)
            
            for result in results_to_show:
                result_item = SearchResultItem(result)
                result_item.download_requested.connect(self.start_download)
                result_item.expansion_requested.connect(self.handle_expansion_request)
                # Insert before the stretch
                insert_position = self.search_results_layout.count() - 1
                self.search_results_layout.insertWidget(insert_position, result_item)
            
            # Re-enable updates and force layout refresh
            self.search_results_widget.setUpdatesEnabled(True)
            self.search_results_widget.updateGeometry()
            self.search_results_layout.update()
            self.search_results_scroll.updateGeometry()
            
            self.displayed_results += len(results_to_show)
        
        # Update status message with real-time feedback
        if self.displayed_results < self.results_per_page:
            self.update_search_status(f"✨ Found {total_count} results so far • Showing first {self.displayed_results}", "#1db954")
        else:
            self.update_search_status(f"✨ Found {total_count} results so far • Showing first {self.results_per_page} (scroll for more)", "#1db954")
    
    def on_search_completed(self, results):
        self.search_btn.setText("🔍 Search")
        self.search_btn.setEnabled(True)
        
        # Use temp results from progressive loading if available, otherwise use results
        if hasattr(self, '_temp_search_results') and self._temp_search_results:
            self.search_results = self._temp_search_results
            del self._temp_search_results  # Clean up temp storage
        else:
            self.search_results = results or []
        
        total_results = len(self.search_results)
        
        if total_results == 0:
            if self.displayed_results == 0:
                self.update_search_status("😔 No results found • Try a different search term or artist name", "#ffa500")
            else:
                self.update_search_status(f"✨ Search completed • Found {self.displayed_results} total results", "#1db954")
            return
        
        # Update status based on whether there are more results to load
        if self.displayed_results < total_results:
            remaining = total_results - self.displayed_results
            self.update_search_status(f"✨ Found {total_results} results • Showing first {self.displayed_results} (scroll down for {remaining} more)", "#1db954")
        else:
            self.update_search_status(f"✨ Search completed • Showing all {total_results} results", "#1db954")
        
        # If we have no displayed results yet, show the first batch
        if self.displayed_results == 0 and total_results > 0:
            self.load_more_results()
    
    def clear_search_results(self):
        """Clear all search result items from the layout"""
        # Remove all SearchResultItem widgets (but keep stretch)
        items_to_remove = []
        for i in range(self.search_results_layout.count()):
            item = self.search_results_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), SearchResultItem):
                items_to_remove.append(item.widget())
        
        for widget in items_to_remove:
            self.search_results_layout.removeWidget(widget)
            widget.deleteLater()
    
    def on_scroll_changed(self, value):
        """Handle scroll changes to implement lazy loading"""
        if self.is_loading_more or not self.search_results:
            return
        
        scroll_bar = self.search_results_scroll.verticalScrollBar()
        
        # Check if we're near the bottom (90% scrolled)
        if scroll_bar.maximum() > 0:
            scroll_percentage = value / scroll_bar.maximum()
            
            if scroll_percentage >= 0.9 and self.displayed_results < len(self.search_results):
                self.load_more_results()
    
    def load_more_results(self):
        """Load the next batch of search results"""
        if self.is_loading_more or not self.search_results:
            return
        
        self.is_loading_more = True
        
        # Calculate how many more results to show
        start_index = self.displayed_results
        end_index = min(start_index + self.results_per_page, len(self.search_results))
        
        # Temporarily disable layout updates for smoother batch loading
        self.search_results_widget.setUpdatesEnabled(False)
        
        # Add result items to UI
        for i in range(start_index, end_index):
            result = self.search_results[i]
            result_item = SearchResultItem(result)
            result_item.download_requested.connect(self.start_download)
            result_item.expansion_requested.connect(self.handle_expansion_request)
            # Insert before the stretch (which is always last)
            insert_position = self.search_results_layout.count() - 1
            self.search_results_layout.insertWidget(insert_position, result_item)
        
        # Re-enable updates and force layout refresh
        self.search_results_widget.setUpdatesEnabled(True)
        self.search_results_widget.updateGeometry()
        self.search_results_layout.update()
        
        # Force scroll area to recognize new content size
        self.search_results_scroll.updateGeometry()
        
        # Update displayed count
        self.displayed_results = end_index
        
        # Update status
        total_results = len(self.search_results)
        if self.displayed_results >= total_results:
            self.update_search_status(f"✨ Showing all {total_results} results", "#1db954")
        else:
            remaining = total_results - self.displayed_results
            self.update_search_status(f"✨ Showing {self.displayed_results} of {total_results} results (scroll for {remaining} more)", "#1db954")
        
        self.is_loading_more = False
    
    def handle_expansion_request(self, requesting_item):
        """Handle accordion-style expansion where only one item can be expanded at a time"""
        # If there's a currently expanded item and it's not the requesting item, collapse it
        if self.currently_expanded_item and self.currently_expanded_item != requesting_item:
            self.currently_expanded_item.set_expanded(False, animate=True)
        
        # Toggle the requesting item
        new_expanded_state = not requesting_item.is_expanded
        requesting_item.set_expanded(new_expanded_state, animate=True)
        
        # Update tracking
        if new_expanded_state:
            self.currently_expanded_item = requesting_item
        else:
            self.currently_expanded_item = None
    
    def on_search_failed(self, error_msg):
        self.search_btn.setText("🔍 Search")
        self.search_btn.setEnabled(True)
        self.update_search_status(f"❌ Search failed: {error_msg}", "#e22134")
    
    def on_search_progress(self, message):
        self.update_search_status(f"🔍 {message}", "#1db954")
    
    def start_download(self, search_result):
        """Start downloading a search result using threaded approach"""
        try:
            # Extract track info for queue display
            filename = search_result.filename
            parts = filename.split(' - ')
            if len(parts) >= 2:
                artist = parts[0].strip()
                title = ' - '.join(parts[1:]).strip()
                # Remove file extension
                if '.' in title:
                    title = '.'.join(title.split('.')[:-1])
            else:
                title = filename
                artist = search_result.username
            
            # Add to download queue immediately as "downloading"
            download_item = self.download_queue.add_download_item(
                title=title,
                artist=artist,
                status="downloading",
                progress=0,
                file_size=search_result.size
            )
            
            # Create and start download thread
            download_thread = DownloadThread(self.soulseek_client, search_result)
            download_thread.download_item = download_item  # Store reference
            download_thread.download_completed.connect(lambda msg, item=download_item: self.on_download_completed(msg, item))
            download_thread.download_failed.connect(lambda msg, item=download_item: self.on_download_failed(msg, item))
            download_thread.download_progress.connect(lambda msg, item=download_item: self.on_download_progress(msg, item))
            download_thread.finished.connect(lambda: self.on_download_thread_finished(download_thread))
            
            # Track the thread
            self.download_threads.append(download_thread)
            
            # Start the download
            download_thread.start()
            
            # Show immediate feedback
            QMessageBox.information(
                self, 
                "Download Started", 
                f"Starting download: {search_result.filename}\n"
                f"From user: {search_result.username}\n\n"
                f"The download will be queued in slskd.\n"
                f"Check the slskd web interface or Downloads page for progress."
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Download Error", f"Failed to start download: {str(e)}")
    
    def on_download_completed(self, message, download_item):
        """Handle successful download start"""
        print(f"Download success: {message}")
        # Update download item status to completed
        download_item.status = "completed"
        download_item.progress = 100
        # TODO: Add actual file path from download result
        
    def on_download_failed(self, error_msg, download_item):
        """Handle download failure"""
        print(f"Download failed: {error_msg}")
        # Update download item status to failed
        download_item.status = "failed"
        download_item.progress = 0
        QMessageBox.critical(self, "Download Failed", f"Download failed: {error_msg}")
    
    def on_download_progress(self, message, download_item):
        """Handle download progress updates"""
        print(f"Download progress: {message}")
        # Extract progress percentage if available from message
        # For now just show as downloading
        download_item.status = "downloading"
    
    def on_download_thread_finished(self, thread):
        """Clean up when download thread finishes"""
        if thread in self.download_threads:
            self.download_threads.remove(thread)
            thread.deleteLater()
    
    def clear_completed_downloads(self):
        """Clear completed downloads from the queue"""
        self.download_queue.clear_completed_downloads()
    
    def update_download_status(self):
        """Poll slskd API for download status updates (QTimer callback)"""
        if not self.soulseek_client or not self.download_queue.download_items:
            return
            
        # Create a thread to handle the async operation
        from PyQt6.QtCore import QThread, pyqtSignal
        
        class StatusUpdateThread(QThread):
            status_updated = pyqtSignal(list)
            
            def __init__(self, soulseek_client):
                super().__init__()
                self.soulseek_client = soulseek_client
                
            def run(self):
                import asyncio
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    downloads = loop.run_until_complete(self.soulseek_client.get_all_downloads())
                    self.status_updated.emit(downloads or [])
                except Exception as e:
                    print(f"Error fetching download status: {e}")
                    self.status_updated.emit([])
                finally:
                    if 'loop' in locals():
                        loop.close()
        
        def handle_status_update(downloads):
            """Handle the download status update in the main thread"""
            try:
                for download_item in self.download_queue.download_items:
                    # Find matching download by filename
                    filename = f"{download_item.artist} - {download_item.title}"
                    
                    for download in downloads:
                        if filename.lower() in download.filename.lower():
                            # Update the UI item with real data
                            download_item.update_status(
                                status=download.state,
                                progress=int(download.progress),
                                download_speed=download.speed,
                                file_path=download.filename
                            )
                            break
            except Exception as e:
                print(f"Error updating download UI: {e}")
        
        # Start the status update thread
        status_thread = StatusUpdateThread(self.soulseek_client)
        status_thread.status_updated.connect(handle_status_update)
        status_thread.finished.connect(status_thread.deleteLater)
        status_thread.start()
    
    
    def cleanup_all_threads(self):
        """Stop and cleanup all active threads"""
        try:
            # Stop search thread
            if self.search_thread and self.search_thread.isRunning():
                self.search_thread.stop()
                self.search_thread.wait(2000)  # Wait up to 2 seconds
                if self.search_thread.isRunning():
                    self.search_thread.terminate()
                    self.search_thread.wait(1000)
                self.search_thread = None
            
            # Stop explore thread
            if self.explore_thread and self.explore_thread.isRunning():
                self.explore_thread.stop()
                self.explore_thread.wait(2000)  # Wait up to 2 seconds
                if self.explore_thread.isRunning():
                    self.explore_thread.terminate()
                    self.explore_thread.wait(1000)
                self.explore_thread = None
            
            # Stop session thread
            if self.session_thread and self.session_thread.isRunning():
                self.session_thread.stop()
                self.session_thread.wait(2000)  # Wait up to 2 seconds
                if self.session_thread.isRunning():
                    self.session_thread.terminate()
                    self.session_thread.wait(1000)
                self.session_thread = None
            
            # Stop all download threads
            for download_thread in self.download_threads[:]:  # Copy list to avoid modification during iteration
                if download_thread.isRunning():
                    download_thread.stop()
                    download_thread.wait(2000)  # Wait up to 2 seconds
                    if download_thread.isRunning():
                        download_thread.terminate()
                        download_thread.wait(1000)
                download_thread.deleteLater()
            
            self.download_threads.clear()
            
        except Exception as e:
            print(f"Error during thread cleanup: {e}")
    
    def closeEvent(self, event):
        """Handle widget close event"""
        self.cleanup_all_threads()
        super().closeEvent(event)
    
    def create_controls_section(self):
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setSpacing(20)
        
        # Download controls
        controls_frame = QFrame()
        controls_frame.setStyleSheet("""
            QFrame {
                background: #282828;
                border-radius: 8px;
                border: 1px solid #404040;
            }
        """)
        
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setContentsMargins(20, 20, 20, 20)
        controls_layout.setSpacing(15)
        
        # Controls title
        controls_title = QLabel("Download Controls")
        controls_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        controls_title.setStyleSheet("color: #ffffff;")
        
        # Pause/Resume button
        pause_btn = QPushButton("⏸️ Pause Downloads")
        pause_btn.setFixedHeight(40)
        pause_btn.setStyleSheet("""
            QPushButton {
                background: #1db954;
                border: none;
                border-radius: 20px;
                color: #000000;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #1ed760;
            }
        """)
        
        # Clear completed button
        clear_btn = QPushButton("🗑️ Clear Completed")
        clear_btn.setFixedHeight(35)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #e22134;
                border-radius: 17px;
                color: #e22134;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(226, 33, 52, 0.1);
            }
        """)
        
        controls_layout.addWidget(controls_title)
        controls_layout.addWidget(pause_btn)
        controls_layout.addWidget(clear_btn)
        
        # Download stats
        stats_frame = QFrame()
        stats_frame.setStyleSheet("""
            QFrame {
                background: #282828;
                border-radius: 8px;
                border: 1px solid #404040;
            }
        """)
        
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setContentsMargins(20, 20, 20, 20)
        stats_layout.setSpacing(15)
        
        # Stats title
        stats_title = QLabel("Download Statistics")
        stats_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        stats_title.setStyleSheet("color: #ffffff;")
        
        # Stats items
        stats_items = [
            ("Total Downloads", "247"),
            ("Completed", "238"),
            ("Failed", "4"),
            ("In Progress", "2"),
            ("Queued", "3")
        ]
        
        stats_layout.addWidget(stats_title)
        
        for label, value in stats_items:
            item_layout = QHBoxLayout()
            
            label_widget = QLabel(label)
            label_widget.setFont(QFont("Arial", 11))
            label_widget.setStyleSheet("color: #b3b3b3;")
            
            value_widget = QLabel(value)
            value_widget.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            value_widget.setStyleSheet("color: #ffffff;")
            
            item_layout.addWidget(label_widget)
            item_layout.addStretch()
            item_layout.addWidget(value_widget)
            
            stats_layout.addLayout(item_layout)
        
        layout.addWidget(controls_frame)
        layout.addWidget(stats_frame)
        layout.addStretch()
        
        return section
    
    def create_missing_tracks_section(self):
        section = QFrame()
        section.setFixedHeight(250)
        section.setStyleSheet("""
            QFrame {
                background: #282828;
                border-radius: 8px;
                border: 1px solid #404040;
            }
        """)
        
        layout = QVBoxLayout(section)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header
        header_layout = QHBoxLayout()
        
        title_label = QLabel("Missing Tracks")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #ffffff;")
        
        count_label = QLabel("23 tracks")
        count_label.setFont(QFont("Arial", 11))
        count_label.setStyleSheet("color: #b3b3b3;")
        
        download_all_btn = QPushButton("📥 Download All")
        download_all_btn.setFixedSize(120, 35)
        download_all_btn.setStyleSheet("""
            QPushButton {
                background: #1db954;
                border: none;
                border-radius: 17px;
                color: #000000;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #1ed760;
            }
        """)
        
        header_layout.addWidget(title_label)
        header_layout.addWidget(count_label)
        header_layout.addStretch()
        header_layout.addWidget(download_all_btn)
        
        # Missing tracks scroll area
        missing_scroll = QScrollArea()
        missing_scroll.setWidgetResizable(True)
        missing_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #404040;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #1db954;
                border-radius: 3px;
            }
        """)
        
        missing_widget = QWidget()
        missing_layout = QVBoxLayout(missing_widget)
        missing_layout.setSpacing(8)
        missing_layout.setContentsMargins(0, 0, 0, 0)
        
        # Sample missing tracks with playlist info
        missing_tracks = [
            ("Song Title 1", "Artist Name 1", "Liked Songs"),
            ("Another Track", "Different Artist", "Road Trip Mix"),
            ("Cool Song", "Band Name", "Workout Playlist"),
            ("Missing Hit", "Popular Artist", "Discover Weekly"),
            ("Rare Track", "Indie Artist", "Chill Vibes")
        ]
        
        for track_title, artist, playlist in missing_tracks:
            track_item = self.create_missing_track_item(track_title, artist, playlist)
            missing_layout.addWidget(track_item)
        
        missing_layout.addStretch()
        missing_scroll.setWidget(missing_widget)
        
        layout.addLayout(header_layout)
        layout.addWidget(missing_scroll)
        
        return section
    
    def create_missing_track_item(self, track_title: str, artist: str, playlist: str):
        item = QFrame()
        item.setFixedHeight(45)
        item.setStyleSheet("""
            QFrame {
                background: #333333;
                border-radius: 6px;
                border: 1px solid #404040;
            }
            QFrame:hover {
                background: #3a3a3a;
                border: 1px solid #1db954;
            }
        """)
        
        layout = QHBoxLayout(item)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)
        
        # Track info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        track_label = QLabel(f"{track_title} - {artist}")
        track_label.setFont(QFont("Arial", 10, QFont.Weight.Medium))
        track_label.setStyleSheet("color: #ffffff;")
        
        playlist_label = QLabel(f"from: {playlist}")
        playlist_label.setFont(QFont("Arial", 9))
        playlist_label.setStyleSheet("color: #1db954;")
        
        info_layout.addWidget(track_label)
        info_layout.addWidget(playlist_label)
        
        # Download button
        download_btn = QPushButton("📥")
        download_btn.setFixedSize(30, 30)
        download_btn.setStyleSheet("""
            QPushButton {
                background: rgba(29, 185, 84, 0.2);
                border: 1px solid #1db954;
                border-radius: 15px;
                color: #1db954;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #1db954;
                color: #000000;
            }
        """)
        
        layout.addLayout(info_layout)
        layout.addStretch()
        layout.addWidget(download_btn)
        
        return item