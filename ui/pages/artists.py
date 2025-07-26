from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                           QFrame, QPushButton, QLineEdit, QScrollArea,
                           QGridLayout, QSizePolicy, QSpacerItem, QApplication,
                           QDialog, QDialogButtonBox, QProgressBar, QMessageBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QObject, QRunnable, QThreadPool, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QFont, QPixmap, QPainter, QPen, QColor
import functools
import os
import threading
import requests
from typing import List, Optional
from dataclasses import dataclass

# Import core components
from core.spotify_client import SpotifyClient, Artist, Album
from core.plex_client import PlexClient
from core.soulseek_client import SoulseekClient, AlbumResult
from core.matching_engine import MusicMatchingEngine

@dataclass
class ArtistMatch:
    """Represents an artist match with confidence score"""
    artist: Artist
    confidence: float
    match_reason: str = ""

class ImageDownloaderSignals(QObject):
    """Signals for the ImageDownloader worker."""
    finished = pyqtSignal(QLabel, QPixmap)
    error = pyqtSignal(str)

class ImageDownloader(QRunnable):
    """Worker to download an image in the background."""
    def __init__(self, url: str, target_label: QLabel):
        super().__init__()
        self.signals = ImageDownloaderSignals()
        self.url = url
        self.target_label = target_label

    def run(self):
        try:
            if not self.url:
                self.signals.error.emit("No image URL provided.")
                return

            response = requests.get(self.url, stream=True, timeout=10)
            response.raise_for_status()
            
            pixmap = QPixmap()
            pixmap.loadFromData(response.content)
            
            if not pixmap.isNull():
                self.signals.finished.emit(self.target_label, pixmap)
            else:
                self.signals.error.emit("Failed to load image from data.")
                
        except requests.RequestException as e:
            self.signals.error.emit(f"Network error downloading image: {e}")
        except Exception as e:
            self.signals.error.emit(f"Error processing image: {e}")

class ArtistSearchWorker(QThread):
    """Background worker for artist search"""
    artists_found = pyqtSignal(list)  # List of ArtistMatch objects
    search_failed = pyqtSignal(str)
    
    def __init__(self, query: str, spotify_client: SpotifyClient, matching_engine: MusicMatchingEngine):
        super().__init__()
        self.query = query
        self.spotify_client = spotify_client
        self.matching_engine = matching_engine
    
    def run(self):
        try:
            # Search for artists using Spotify
            artists = self.spotify_client.search_artists(self.query, limit=10)
            
            # Create artist matches with confidence scores
            artist_matches = []
            for artist in artists:
                # Calculate confidence based on name similarity
                confidence = self.matching_engine.similarity_score(self.query.lower(), artist.name.lower())
                match = ArtistMatch(
                    artist=artist,
                    confidence=confidence,
                    match_reason=f"Name similarity: {confidence:.1%}"
                )
                artist_matches.append(match)
            
            # Sort by confidence score
            artist_matches.sort(key=lambda x: x.confidence, reverse=True)
            
            self.artists_found.emit(artist_matches)
            
        except Exception as e:
            self.search_failed.emit(str(e))

class AlbumFetchWorker(QThread):
    """Background worker for fetching artist albums"""
    albums_found = pyqtSignal(list, object)  # List of albums, selected artist
    fetch_failed = pyqtSignal(str)
    
    def __init__(self, artist: Artist, spotify_client: SpotifyClient):
        super().__init__()
        self.artist = artist
        self.spotify_client = spotify_client
    
    def run(self):
        try:
            print(f"🎵 Fetching albums for artist: {self.artist.name} (ID: {self.artist.id})")
            
            # Use the proper Spotify API method to get albums by artist
            albums = self.spotify_client.get_artist_albums(self.artist.id, album_type='album', limit=50)
            
            print(f"📀 Found {len(albums)} albums for {self.artist.name}")
            
            if not albums:
                print("⚠️ No albums found, trying with singles included...")
                # If no albums found, try including singles
                albums = self.spotify_client.get_artist_albums(self.artist.id, album_type='album,single', limit=50)
                print(f"📀 Found {len(albums)} items including singles")
            
            # Remove duplicates based on name (case insensitive)
            seen_names = set()
            unique_albums = []
            for album in albums:
                album_name_lower = album.name.lower()
                if album_name_lower not in seen_names:
                    seen_names.add(album_name_lower)
                    unique_albums.append(album)
            
            # Sort by release date (newest first)
            unique_albums.sort(key=lambda x: x.release_date if x.release_date else '', reverse=True)
            
            print(f"✅ Returning {len(unique_albums)} unique albums")
            self.albums_found.emit(unique_albums, self.artist)
            
        except Exception as e:
            error_msg = f"Failed to fetch albums for {self.artist.name}: {str(e)}"
            print(f"❌ {error_msg}")
            self.fetch_failed.emit(error_msg)

class AlbumSearchWorker(QThread):
    """Background worker for searching albums on Soulseek"""
    search_results = pyqtSignal(list)  # List of AlbumResult objects
    search_failed = pyqtSignal(str)
    search_progress = pyqtSignal(str)  # Progress messages
    
    def __init__(self, album: Album, soulseek_client: SoulseekClient):
        super().__init__()
        self.album = album
        self.soulseek_client = soulseek_client
        self._stop_requested = False
    
    def stop(self):
        """Request to stop the search"""
        self._stop_requested = True
    
    def run(self):
        try:
            if not self.soulseek_client:
                self.search_failed.emit("Soulseek client not available")
                return
            
            # Create search query for the album
            search_query = f'"{self.album.name}"'
            if self.album.artists:
                search_query = f'"{self.album.artists[0]}" "{self.album.name}"'
            
            self.search_progress.emit(f"Searching for: {search_query}")
            
            # Perform the search
            results = self.soulseek_client.search(search_query)
            
            if self._stop_requested:
                return
            
            # Filter to album results only
            album_results = []
            if results:
                tracks, albums = results  # Unpack the tuple returned by search
                album_results = albums if albums else []
            
            # Sort by quality/size
            album_results.sort(key=lambda x: (x.total_size, x.track_count), reverse=True)
            
            self.search_results.emit(album_results)
            
        except Exception as e:
            if not self._stop_requested:
                self.search_failed.emit(str(e))

class PlexLibraryWorker(QThread):
    """Background worker for checking Plex library"""
    library_checked = pyqtSignal(set)  # Set of owned album names
    check_failed = pyqtSignal(str)
    
    def __init__(self, albums, plex_client, matching_engine):
        super().__init__()
        self.albums = albums
        self.plex_client = plex_client
        self.matching_engine = matching_engine
        self._stop_requested = False
    
    def stop(self):
        """Request to stop the check"""
        self._stop_requested = True
    
    def run(self):
        try:
            print("🔍 Starting Plex library check...")
            owned_albums = set()
            
            if not self.plex_client or not self.plex_client.ensure_connection():
                print("⚠️ Plex client not available or not connected")
                self.library_checked.emit(owned_albums)
                return
            
            if self._stop_requested:
                return
            
            # Get a smaller sample of tracks to avoid loading 10,000 items
            print("📚 Searching Plex library for albums...")
            plex_tracks = self.plex_client.search_tracks("", "", limit=1000)  # Reduced from 10000
            
            if self._stop_requested:
                return
            
            # Extract unique album names from Plex
            plex_album_names = set()
            for track in plex_tracks:
                if self._stop_requested:
                    return
                    
                if track.album and track.album != "Unknown Album":
                    plex_album_names.add(track.album.lower())
            
            print(f"📀 Found {len(plex_album_names)} unique albums in Plex library")
            
            # Check each Spotify album against Plex albums
            for album in self.albums:
                if self._stop_requested:
                    return
                    
                album_name_lower = album.name.lower()
                for plex_album in plex_album_names:
                    if self.matching_engine.similarity_score(album_name_lower, plex_album) > 0.8:
                        owned_albums.add(album.name)
                        break
            
            print(f"✅ Found {len(owned_albums)} owned albums")
            self.library_checked.emit(owned_albums)
            
        except Exception as e:
            if not self._stop_requested:
                error_msg = f"Error checking Plex library: {e}"
                print(f"❌ {error_msg}")
                self.check_failed.emit(error_msg)

class AlbumSearchDialog(QDialog):
    """Dialog for displaying album search results and allowing selection"""
    album_selected = pyqtSignal(object)  # AlbumResult object
    
    def __init__(self, album: Album, parent=None):
        super().__init__(parent)
        self.album = album
        self.selected_album_result = None
        self.search_worker = None
        self.setup_ui()
        self.start_search()
    
    def setup_ui(self):
        self.setWindowTitle(f"Download Album: {self.album.name}")
        self.setFixedSize(600, 500)
        self.setStyleSheet("""
            QDialog {
                background: #191414;
                color: #ffffff;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Header
        header_label = QLabel(f"Searching for: {self.album.name}")
        header_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_label.setStyleSheet("color: #ffffff; padding: 8px;")
        
        artist_label = QLabel(f"By: {', '.join(self.album.artists)}")
        artist_label.setFont(QFont("Arial", 11))
        artist_label.setStyleSheet("color: #b3b3b3; padding: 4px;")
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #404040;
                border-radius: 4px;
                background: #282828;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background: #1db954;
                border-radius: 3px;
            }
        """)
        
        # Status label
        self.status_label = QLabel("Initializing search...")
        self.status_label.setFont(QFont("Arial", 10))
        self.status_label.setStyleSheet("color: #b3b3b3; padding: 4px;")
        
        # Results area
        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #404040;
                border-radius: 8px;
                background: #282828;
            }
            QScrollBar:vertical {
                background: #404040;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #1db954;
                border-radius: 6px;
                min-height: 20px;
            }
        """)
        
        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setSpacing(8)
        self.results_layout.setContentsMargins(12, 12, 12, 12)
        
        self.results_scroll.setWidget(self.results_widget)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.cancel_search_btn = QPushButton("Cancel Search")
        self.cancel_search_btn.setStyleSheet("""
            QPushButton {
                background: #ff6b6b;
                border: none;
                border-radius: 6px;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: #ff5252;
            }
        """)
        self.cancel_search_btn.clicked.connect(self.cancel_search)
        
        self.download_btn = QPushButton("Download Selected")
        self.download_btn.setEnabled(False)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background: #1db954;
                border: none;
                border-radius: 6px;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: #1ed760;
            }
            QPushButton:disabled {
                background: #404040;
                color: #808080;
            }
        """)
        self.download_btn.clicked.connect(self.download_selected)
        
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("""
            QPushButton {
                background: #404040;
                border: none;
                border-radius: 6px;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: #505050;
            }
        """)
        close_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.cancel_search_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.download_btn)
        button_layout.addWidget(close_btn)
        
        # Add to main layout
        layout.addWidget(header_label)
        layout.addWidget(artist_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        layout.addWidget(self.results_scroll, 1)
        layout.addLayout(button_layout)
    
    def start_search(self):
        """Start the album search"""
        # We need to get the soulseek client from the parent
        parent_page = self.parent()
        if hasattr(parent_page, 'soulseek_client') and parent_page.soulseek_client:
            self.search_worker = AlbumSearchWorker(self.album, parent_page.soulseek_client)
            self.search_worker.search_results.connect(self.on_search_results)
            self.search_worker.search_failed.connect(self.on_search_failed)
            self.search_worker.search_progress.connect(self.on_search_progress)
            self.search_worker.finished.connect(self.on_search_finished)
            self.search_worker.start()
        else:
            self.on_search_failed("Soulseek client not available")
    
    def cancel_search(self):
        """Cancel the current search"""
        if self.search_worker:
            self.search_worker.stop()
            self.search_worker.terminate()
            self.search_worker.wait()
        self.reject()
    
    def on_search_progress(self, message):
        """Handle search progress updates"""
        self.status_label.setText(message)
    
    def on_search_results(self, album_results):
        """Handle search results"""
        if not album_results:
            self.status_label.setText("No albums found")
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(1)
            return
        
        self.status_label.setText(f"Found {len(album_results)} albums")
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        
        # Display results
        for i, album_result in enumerate(album_results[:10]):  # Show top 10 results
            result_item = self.create_result_item(album_result, i)
            self.results_layout.addWidget(result_item)
        
        self.results_layout.addStretch()
        self.cancel_search_btn.setText("Cancel")
    
    def on_search_failed(self, error):
        """Handle search failure"""
        self.status_label.setText(f"Search failed: {error}")
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.cancel_search_btn.setText("Close")
    
    def on_search_finished(self):
        """Handle search completion"""
        self.cancel_search_btn.setText("Close")
    
    def create_result_item(self, album_result: AlbumResult, index: int):
        """Create a result item widget"""
        item = QFrame()
        item.setStyleSheet("""
            QFrame {
                background: rgba(40, 40, 40, 0.8);
                border: 1px solid #606060;
                border-radius: 8px;
                padding: 8px;
            }
            QFrame:hover {
                background: rgba(50, 50, 50, 0.9);
                border: 1px solid #1db954;
            }
        """)
        item.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QHBoxLayout(item)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        
        # Album info
        info_layout = QVBoxLayout()
        
        title_label = QLabel(album_result.album_title)
        title_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #ffffff;")
        
        details_label = QLabel(f"By: {album_result.artist} • {album_result.track_count} tracks • {self.format_size(album_result.total_size)}")
        details_label.setFont(QFont("Arial", 9))
        details_label.setStyleSheet("color: #b3b3b3;")
        
        uploader_label = QLabel(f"Uploader: {album_result.username}")
        uploader_label.setFont(QFont("Arial", 8))
        uploader_label.setStyleSheet("color: #888888;")
        
        info_layout.addWidget(title_label)
        info_layout.addWidget(details_label)
        info_layout.addWidget(uploader_label)
        
        # Select button
        select_btn = QPushButton("Select")
        select_btn.setFixedWidth(80)
        select_btn.setStyleSheet("""
            QPushButton {
                background: #1db954;
                border: none;
                border-radius: 4px;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background: #1ed760;
            }
        """)
        select_btn.clicked.connect(lambda: self.select_result(album_result))
        
        layout.addLayout(info_layout)
        layout.addStretch()
        layout.addWidget(select_btn)
        
        return item
    
    def format_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes >= 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
        elif size_bytes >= 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        elif size_bytes >= 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes} B"
    
    def select_result(self, album_result):
        """Select an album result"""
        self.selected_album_result = album_result
        self.download_btn.setEnabled(True)
        
        # Visual feedback - highlight selected item
        for i in range(self.results_layout.count()):
            item = self.results_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if hasattr(widget, 'setStyleSheet'):
                    if widget.layout() and widget.layout().itemAt(2) and widget.layout().itemAt(2).widget():
                        btn = widget.layout().itemAt(2).widget()
                        if btn.text() == "Select":
                            widget.setStyleSheet("""
                                QFrame {
                                    background: rgba(40, 40, 40, 0.8);
                                    border: 1px solid #606060;
                                    border-radius: 8px;
                                    padding: 8px;
                                }
                            """)
                            btn.setText("Select")
        
        # Highlight the selected item
        sender = self.sender()
        if sender:
            parent_frame = sender.parent()
            if parent_frame:
                parent_frame.setStyleSheet("""
                    QFrame {
                        background: rgba(29, 185, 84, 0.3);
                        border: 2px solid #1db954;
                        border-radius: 8px;
                        padding: 8px;
                    }
                """)
                sender.setText("Selected ✓")
    
    def download_selected(self):
        """Download the selected album"""
        if self.selected_album_result:
            self.album_selected.emit(self.selected_album_result)
            self.accept()
    
    def closeEvent(self, event):
        """Handle dialog close"""
        if self.search_worker:
            self.search_worker.stop()
            self.search_worker.terminate()
            self.search_worker.wait()
        super().closeEvent(event)

class ArtistResultCard(QFrame):
    """Card widget for displaying artist search results"""
    artist_selected = pyqtSignal(object)  # Artist object
    
    def __init__(self, artist_match: ArtistMatch, parent=None):
        super().__init__(parent)
        self.artist_match = artist_match
        self.artist = artist_match.artist
        self.setup_ui()
        self.load_artist_image()
    
    def setup_ui(self):
        self.setFixedSize(200, 280)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Base styling with gradient background
        self.setStyleSheet("""
            ArtistResultCard {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(45, 45, 45, 0.95),
                    stop:1 rgba(35, 35, 35, 0.98));
                border-radius: 12px;
                border: 2px solid rgba(80, 80, 80, 0.4);
            }
            ArtistResultCard:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(29, 185, 84, 0.2),
                    stop:1 rgba(24, 156, 71, 0.3));
                border: 2px solid rgba(29, 185, 84, 0.8);
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # Artist image container
        self.image_container = QFrame()
        self.image_container.setFixedSize(176, 176)
        self.image_container.setStyleSheet("""
            QFrame {
                background: #404040;
                border-radius: 88px;
                border: 2px solid #606060;
            }
        """)
        
        image_layout = QVBoxLayout(self.image_container)
        image_layout.setContentsMargins(0, 0, 0, 0)
        
        self.image_label = QLabel()
        self.image_label.setFixedSize(172, 172)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                background: transparent;
                border-radius: 86px;
                color: #b3b3b3;
                font-size: 48px;
            }
        """)
        self.image_label.setText("🎵")
        
        image_layout.addWidget(self.image_label)
        
        # Artist name
        name_label = QLabel(self.artist.name)
        name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        name_label.setStyleSheet("color: #ffffff; padding: 4px;")
        name_label.setWordWrap(True)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Confidence score
        confidence_label = QLabel(f"Match: {self.artist_match.confidence:.0%}")
        confidence_label.setFont(QFont("Arial", 9))
        confidence_label.setStyleSheet("color: #1db954; padding: 2px;")
        confidence_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Followers count
        followers_text = self.format_followers(self.artist.followers)
        followers_label = QLabel(f"{followers_text} followers")
        followers_label.setFont(QFont("Arial", 8))
        followers_label.setStyleSheet("color: #b3b3b3; padding: 2px;")
        followers_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.image_container, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)
        layout.addWidget(confidence_label)
        layout.addWidget(followers_label)
        layout.addStretch()
    
    def format_followers(self, count: int) -> str:
        """Format follower count in human readable format"""
        if count >= 1000000:
            return f"{count / 1000000:.1f}M"
        elif count >= 1000:
            return f"{count / 1000:.1f}K"
        else:
            return str(count)
    
    def load_artist_image(self):
        """Load artist image in background"""
        if self.artist.image_url:
            downloader = ImageDownloader(self.artist.image_url, self.image_label)
            downloader.signals.finished.connect(self.on_image_loaded)
            downloader.signals.error.connect(self.on_image_error)
            QThreadPool.globalInstance().start(downloader)
    
    def on_image_loaded(self, label, pixmap):
        """Handle successful image load"""
        if label == self.image_label:
            # Scale and mask the image to fit the circular container
            scaled_pixmap = pixmap.scaled(172, 172, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            
            # Create circular mask
            masked_pixmap = QPixmap(172, 172)
            masked_pixmap.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(masked_pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(255, 255, 255))
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.drawEllipse(0, 0, 172, 172)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.drawPixmap(0, 0, scaled_pixmap)
            painter.end()
            
            self.image_label.setPixmap(masked_pixmap)
    
    def on_image_error(self, error):
        """Handle image load error"""
        print(f"Failed to load artist image: {error}")
    
    def mousePressEvent(self, event):
        """Handle click to select artist"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.artist_selected.emit(self.artist)
        super().mousePressEvent(event)

class AlbumCard(QFrame):
    """Card widget for displaying album information"""
    download_requested = pyqtSignal(object)  # Album object
    
    def __init__(self, album: Album, is_owned: bool = False, parent=None):
        super().__init__(parent)
        self.album = album
        self.is_owned = is_owned
        self.setup_ui()
        self.load_album_image()
    
    def setup_ui(self):
        self.setFixedSize(180, 240)
        
        self.setStyleSheet("""
            AlbumCard {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(40, 40, 40, 0.9),
                    stop:1 rgba(30, 30, 30, 0.95));
                border-radius: 10px;
                border: 1px solid rgba(70, 70, 70, 0.5);
            }
            AlbumCard:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(50, 50, 50, 0.95),
                    stop:1 rgba(40, 40, 40, 0.98));
                border: 1px solid rgba(29, 185, 84, 0.6);
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        # Album image container
        self.image_container = QFrame()
        self.image_container.setFixedSize(164, 164)
        self.image_container.setStyleSheet("""
            QFrame {
                background: #404040;
                border-radius: 6px;
                border: 1px solid #606060;
            }
        """)
        
        image_layout = QVBoxLayout(self.image_container)
        image_layout.setContentsMargins(0, 0, 0, 0)
        
        self.image_label = QLabel()
        self.image_label.setFixedSize(162, 162)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                background: transparent;
                border-radius: 5px;
                color: #b3b3b3;
                font-size: 32px;
            }
        """)
        self.image_label.setText("💿")
        
        image_layout.addWidget(self.image_label)
        
        # Overlay for ownership status
        self.overlay = QLabel(self.image_container)
        self.overlay.setFixedSize(164, 164)
        self.overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if self.is_owned:
            self.overlay.setStyleSheet("""
                QLabel {
                    background: rgba(29, 185, 84, 0.8);
                    border-radius: 6px;
                    color: white;
                    font-size: 24px;
                    font-weight: bold;
                }
            """)
            self.overlay.setText("✓")
        else:
            self.overlay.setStyleSheet("""
                QLabel {
                    background: rgba(0, 0, 0, 0.7);
                    border-radius: 6px;
                    color: white;
                    font-size: 16px;
                    font-weight: bold;
                }
            """)
            self.overlay.setText("📥\nDownload")
            self.overlay.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.overlay.hide()  # Initially hidden, shown on hover
        
        # Album name
        album_label = QLabel(self.album.name)
        album_label.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        album_label.setStyleSheet("color: #ffffff; padding: 2px;")
        album_label.setWordWrap(True)
        album_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        album_label.setMaximumHeight(32)
        
        # Release year
        year_label = QLabel(self.album.release_date[:4] if self.album.release_date else "Unknown")
        year_label.setFont(QFont("Arial", 8))
        year_label.setStyleSheet("color: #b3b3b3; padding: 1px;")
        year_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.image_container, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(album_label)
        layout.addWidget(year_label)
        layout.addStretch()
    
    def load_album_image(self):
        """Load album image in background"""
        if self.album.image_url:
            downloader = ImageDownloader(self.album.image_url, self.image_label)
            downloader.signals.finished.connect(self.on_image_loaded)
            downloader.signals.error.connect(self.on_image_error)
            QThreadPool.globalInstance().start(downloader)
    
    def on_image_loaded(self, label, pixmap):
        """Handle successful image load"""
        if label == self.image_label:
            scaled_pixmap = pixmap.scaled(162, 162, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)
    
    def on_image_error(self, error):
        """Handle image load error"""
        print(f"Failed to load album image: {error}")
    
    def enterEvent(self, event):
        """Show overlay on hover"""
        self.overlay.show()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Hide overlay when not hovering"""
        self.overlay.hide()
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        """Handle click for download"""
        if event.button() == Qt.MouseButton.LeftButton and not self.is_owned:
            self.download_requested.emit(self.album)
        super().mousePressEvent(event)

class ArtistsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Core clients
        self.spotify_client = None
        self.plex_client = None
        self.soulseek_client = None
        self.matching_engine = MusicMatchingEngine()
        
        # State management
        self.selected_artist = None
        self.current_albums = []
        self.artist_search_worker = None
        self.album_fetch_worker = None
        self.plex_library_worker = None
        
        # UI setup
        self.setup_ui()
        self.setup_clients()
    
    def setup_clients(self):
        """Initialize client connections"""
        try:
            self.spotify_client = SpotifyClient()
            self.plex_client = PlexClient()
            self.soulseek_client = SoulseekClient()
        except Exception as e:
            print(f"Failed to initialize clients: {e}")
    
    def setup_ui(self):
        self.setStyleSheet("""
            ArtistsPage {
                background: #191414;
            }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)
        
        # Create main container for dynamic content switching
        self.main_container = QWidget()
        container_layout = QVBoxLayout(self.main_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # Initial centered search interface
        self.search_interface = self.create_search_interface()
        container_layout.addWidget(self.search_interface)
        
        # Artist view (initially hidden)
        self.artist_view = self.create_artist_view()
        self.artist_view.hide()
        container_layout.addWidget(self.artist_view)
        
        main_layout.addWidget(self.main_container)
    
    def create_search_interface(self):
        """Create the initial centered search interface"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Add vertical stretch to center content
        layout.addStretch(2)
        
        # Title section
        title_container = QWidget()
        title_layout = QVBoxLayout(title_container)
        title_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_layout.setSpacing(10)
        
        title_label = QLabel("Discover Artists")
        title_label.setFont(QFont("Arial", 32, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #ffffff;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        subtitle_label = QLabel("Search for any artist to explore their complete discography")
        subtitle_label.setFont(QFont("Arial", 16))
        subtitle_label.setStyleSheet("color: #b3b3b3;")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)
        
        # Search bar
        search_container = QFrame()
        search_container.setFixedHeight(80)
        search_container.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(50, 50, 50, 0.9),
                    stop:1 rgba(40, 40, 40, 0.95));
                border-radius: 16px;
                border: 2px solid rgba(29, 185, 84, 0.3);
            }
        """)
        
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(24, 20, 24, 20)
        search_layout.setSpacing(16)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for an artist... (e.g., 'The Beatles', 'Taylor Swift')")
        self.search_input.setFixedHeight(40)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: rgba(70, 70, 70, 0.8);
                border: 2px solid rgba(100, 100, 100, 0.3);
                border-radius: 20px;
                padding: 0 20px;
                color: #ffffff;
                font-size: 16px;
                font-weight: 500;
            }
            QLineEdit:focus {
                border: 2px solid rgba(29, 185, 84, 0.8);
                background: rgba(80, 80, 80, 0.9);
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.5);
            }
        """)
        self.search_input.returnPressed.connect(self.perform_artist_search)
        
        search_btn = QPushButton("🔍 Search Artists")
        search_btn.setFixedHeight(40)
        search_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(29, 185, 84, 1.0),
                    stop:1 rgba(24, 156, 71, 1.0));
                border: none;
                border-radius: 20px;
                color: #000000;
                font-size: 14px;
                font-weight: bold;
                padding: 0 24px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(30, 215, 96, 1.0),
                    stop:1 rgba(26, 174, 81, 1.0));
            }
        """)
        search_btn.clicked.connect(self.perform_artist_search)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_btn)
        
        # Status label
        self.search_status = QLabel("Ready to search")
        self.search_status.setFont(QFont("Arial", 12))
        self.search_status.setStyleSheet("color: rgba(255, 255, 255, 0.7); padding: 10px;")
        self.search_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Artist results container (initially hidden)
        self.artist_results_container = QFrame()
        self.artist_results_container.setStyleSheet("""
            QFrame {
                background: rgba(30, 30, 30, 0.6);
                border-radius: 12px;
                border: 1px solid rgba(60, 60, 60, 0.4);
            }
        """)
        self.artist_results_container.hide()
        
        results_layout = QVBoxLayout(self.artist_results_container)
        results_layout.setContentsMargins(20, 16, 20, 20)
        results_layout.setSpacing(16)
        
        results_header = QLabel("Artist Results")
        results_header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        results_header.setStyleSheet("color: #ffffff;")
        
        results_layout.addWidget(results_header)
        
        # Scrollable artist results
        self.artist_scroll = QScrollArea()
        self.artist_scroll.setWidgetResizable(True)
        self.artist_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.artist_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.artist_scroll.setMaximumHeight(400)
        self.artist_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: rgba(80, 80, 80, 0.3);
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(29, 185, 84, 0.8);
                border-radius: 4px;
                min-height: 20px;
            }
        """)
        
        self.artist_results_widget = QWidget()
        self.artist_results_layout = QHBoxLayout(self.artist_results_widget)
        self.artist_results_layout.setSpacing(16)
        self.artist_results_layout.setContentsMargins(0, 0, 0, 0)
        
        self.artist_scroll.setWidget(self.artist_results_widget)
        results_layout.addWidget(self.artist_scroll)
        
        # Add everything to main layout
        layout.addWidget(title_container)
        layout.addSpacing(40)
        layout.addWidget(search_container)
        layout.addSpacing(20)
        layout.addWidget(self.search_status)
        layout.addSpacing(20)
        layout.addWidget(self.artist_results_container)
        layout.addStretch(2)
        
        return widget
    
    def create_artist_view(self):
        """Create the artist view for displaying albums"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)
        
        # Header with artist info and repositioned search
        header = QFrame()
        header.setFixedHeight(100)
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(40, 40, 40, 0.9),
                    stop:1 rgba(30, 30, 30, 0.95));
                border-radius: 12px;
                border: 1px solid rgba(60, 60, 60, 0.4);
            }
        """)
        
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 20, 16)
        header_layout.setSpacing(20)
        
        # Artist info section
        artist_info_layout = QVBoxLayout()
        
        self.artist_name_label = QLabel()
        self.artist_name_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self.artist_name_label.setStyleSheet("color: #ffffff;")
        
        self.artist_stats_label = QLabel()
        self.artist_stats_label.setFont(QFont("Arial", 11))
        self.artist_stats_label.setStyleSheet("color: #b3b3b3;")
        
        artist_info_layout.addWidget(self.artist_name_label)
        artist_info_layout.addWidget(self.artist_stats_label)
        
        # New search bar (smaller, in header)
        self.header_search_input = QLineEdit()
        self.header_search_input.setPlaceholderText("Search for another artist...")
        self.header_search_input.setFixedHeight(36)
        self.header_search_input.setFixedWidth(300)
        self.header_search_input.setStyleSheet("""
            QLineEdit {
                background: rgba(60, 60, 60, 0.8);
                border: 1px solid rgba(100, 100, 100, 0.4);
                border-radius: 18px;
                padding: 0 16px;
                color: #ffffff;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid rgba(29, 185, 84, 0.8);
            }
        """)
        self.header_search_input.returnPressed.connect(self.perform_new_artist_search)
        
        # Back button
        back_btn = QPushButton("← Back to Search")
        back_btn.setFixedHeight(36)
        back_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid rgba(29, 185, 84, 0.6);
                border-radius: 18px;
                color: #1db954;
                font-size: 12px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background: rgba(29, 185, 84, 0.1);
            }
        """)
        back_btn.clicked.connect(self.return_to_search)
        
        header_layout.addLayout(artist_info_layout)
        header_layout.addStretch()
        header_layout.addWidget(self.header_search_input)
        header_layout.addWidget(back_btn)
        
        # Albums section
        albums_container = QFrame()
        albums_container.setStyleSheet("""
            QFrame {
                background: rgba(25, 25, 25, 0.6);
                border-radius: 12px;
                border: 1px solid rgba(50, 50, 50, 0.4);
            }
        """)
        
        albums_layout = QVBoxLayout(albums_container)
        albums_layout.setContentsMargins(20, 16, 20, 20)
        albums_layout.setSpacing(16)
        
        # Albums header
        albums_header_layout = QHBoxLayout()
        
        albums_title = QLabel("Albums")
        albums_title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        albums_title.setStyleSheet("color: #ffffff;")
        
        self.albums_status = QLabel("Loading albums...")
        self.albums_status.setFont(QFont("Arial", 11))
        self.albums_status.setStyleSheet("color: #b3b3b3;")
        
        albums_header_layout.addWidget(albums_title)
        albums_header_layout.addStretch()
        albums_header_layout.addWidget(self.albums_status)
        
        albums_layout.addLayout(albums_header_layout)
        
        # Albums grid
        self.albums_scroll = QScrollArea()
        self.albums_scroll.setWidgetResizable(True)
        self.albums_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.albums_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.albums_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: rgba(80, 80, 80, 0.3);
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(29, 185, 84, 0.8);
                border-radius: 4px;
                min-height: 20px;
            }
        """)
        
        self.albums_widget = QWidget()
        self.albums_grid_layout = QGridLayout(self.albums_widget)
        self.albums_grid_layout.setSpacing(16)
        self.albums_grid_layout.setContentsMargins(0, 0, 0, 0)
        
        self.albums_scroll.setWidget(self.albums_widget)
        albums_layout.addWidget(self.albums_scroll)
        
        layout.addWidget(header)
        layout.addWidget(albums_container, 1)
        
        return widget
    
    def perform_artist_search(self):
        """Perform artist search"""
        query = self.search_input.text().strip()
        if not query:
            self.search_status.setText("Please enter an artist name")
            self.search_status.setStyleSheet("color: #ff6b6b; padding: 10px;")
            return
        
        if not self.spotify_client or not self.spotify_client.is_authenticated():
            self.search_status.setText("Spotify not connected")
            self.search_status.setStyleSheet("color: #ff6b6b; padding: 10px;")
            return
        
        self.search_status.setText("🔍 Searching for artists...")
        self.search_status.setStyleSheet("color: #1db954; padding: 10px;")
        
        # Clear previous results
        self.clear_artist_results()
        
        # Start search worker
        if self.artist_search_worker:
            self.artist_search_worker.terminate()
            self.artist_search_worker.wait()
        
        self.artist_search_worker = ArtistSearchWorker(query, self.spotify_client, self.matching_engine)
        self.artist_search_worker.artists_found.connect(self.on_artists_found)
        self.artist_search_worker.search_failed.connect(self.on_artist_search_failed)
        self.artist_search_worker.start()
    
    def perform_new_artist_search(self):
        """Perform new artist search from header"""
        query = self.header_search_input.text().strip()
        if query:
            self.search_input.setText(query)
            self.return_to_search()
            QTimer.singleShot(100, self.perform_artist_search)
    
    def on_artists_found(self, artist_matches):
        """Handle artist search results"""
        if not artist_matches:
            self.search_status.setText("No artists found")
            self.search_status.setStyleSheet("color: #ff6b6b; padding: 10px;")
            return
        
        self.search_status.setText(f"Found {len(artist_matches)} artists")
        self.search_status.setStyleSheet("color: #1db954; padding: 10px;")
        
        # Display artist results
        for artist_match in artist_matches[:10]:  # Show top 10 results
            card = ArtistResultCard(artist_match)
            card.artist_selected.connect(self.on_artist_selected)
            self.artist_results_layout.addWidget(card)
        
        self.artist_results_layout.addStretch()
        self.artist_results_container.show()
    
    def on_artist_search_failed(self, error):
        """Handle artist search failure"""
        self.search_status.setText(f"Search failed: {error}")
        self.search_status.setStyleSheet("color: #ff6b6b; padding: 10px;")
    
    def on_artist_selected(self, artist):
        """Handle artist selection"""
        self.selected_artist = artist
        
        # Update artist view
        self.artist_name_label.setText(artist.name)
        self.artist_stats_label.setText(f"{artist.followers:,} followers • {len(artist.genres)} genres")
        
        # Switch to artist view
        self.search_interface.hide()
        self.artist_view.show()
        
        # Start fetching albums
        self.fetch_artist_albums(artist)
    
    def fetch_artist_albums(self, artist):
        """Fetch albums for selected artist"""
        self.albums_status.setText("Loading albums...")
        
        # Clear previous albums
        self.clear_albums()
        
        # Start album fetch worker
        if self.album_fetch_worker:
            self.album_fetch_worker.terminate()
            self.album_fetch_worker.wait()
        
        self.album_fetch_worker = AlbumFetchWorker(artist, self.spotify_client)
        self.album_fetch_worker.albums_found.connect(self.on_albums_found)
        self.album_fetch_worker.fetch_failed.connect(self.on_album_fetch_failed)
        self.album_fetch_worker.start()
    
    def on_albums_found(self, albums, artist):
        """Handle album fetch results"""
        if not albums:
            self.albums_status.setText("No albums found")
            return
        
        self.current_albums = albums
        self.albums_status.setText(f"Found {len(albums)} albums • Checking Plex library...")
        
        # Display albums first (without ownership info)
        self.display_albums(albums, set())
        
        # Start Plex library check in background
        self.start_plex_library_check(albums)
    
    def display_albums(self, albums, owned_albums):
        """Display albums in the grid"""
        # Clear existing albums
        self.clear_albums()
        
        row, col = 0, 0
        max_cols = 5
        
        for album in albums:
            is_owned = album.name in owned_albums
            card = AlbumCard(album, is_owned)
            if not is_owned:
                card.download_requested.connect(self.on_album_download_requested)
            
            self.albums_grid_layout.addWidget(card, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
    
    def start_plex_library_check(self, albums):
        """Start Plex library check in background"""
        # Stop any existing Plex worker
        if self.plex_library_worker:
            self.plex_library_worker.stop()
            self.plex_library_worker.terminate()
            self.plex_library_worker.wait()
        
        # Start new Plex worker
        self.plex_library_worker = PlexLibraryWorker(albums, self.plex_client, self.matching_engine)
        self.plex_library_worker.library_checked.connect(self.on_plex_library_checked)
        self.plex_library_worker.check_failed.connect(self.on_plex_library_check_failed)
        self.plex_library_worker.start()
    
    def on_plex_library_checked(self, owned_albums):
        """Handle Plex library check results"""
        if self.current_albums:
            # Update the status
            owned_count = len(owned_albums)
            total_count = len(self.current_albums)
            missing_count = total_count - owned_count
            
            self.albums_status.setText(f"Found {total_count} albums • {owned_count} owned • {missing_count} available for download")
            
            # Refresh the display with ownership info
            self.display_albums(self.current_albums, owned_albums)
    
    def on_plex_library_check_failed(self, error):
        """Handle Plex library check failure"""
        print(f"Plex library check failed: {error}")
        if self.current_albums:
            self.albums_status.setText(f"Found {len(self.current_albums)} albums • Plex check failed")
            # Display albums without ownership info
            self.display_albums(self.current_albums, set())
    
    def on_album_fetch_failed(self, error):
        """Handle album fetch failure"""
        self.albums_status.setText(f"Failed to load albums: {error}")
    
    
    def on_album_download_requested(self, album):
        """Handle album download request"""
        print(f"Download requested for album: {album.name} by {', '.join(album.artists)}")
        
        # Open the album search dialog
        dialog = AlbumSearchDialog(album, self)
        dialog.album_selected.connect(self.on_album_selected_for_download)
        dialog.exec()
    
    def on_album_selected_for_download(self, album_result: AlbumResult):
        """Handle album selection from search dialog"""
        print(f"Selected album for download: {album_result.album_title} by {album_result.artist}")
        
        # Start download process for the selected album
        self.start_album_download(album_result)
    
    def start_album_download(self, album_result: AlbumResult):
        """Start downloading the selected album"""
        try:
            if not self.soulseek_client:
                QMessageBox.warning(self, "Error", "Soulseek client not available!")
                return
            
            # Create download items for each track in the album
            for track in album_result.tracks:
                # Create a unique download ID
                download_id = f"{album_result.username}_{track.filename}"
                
                # Add to download queue (we need to integrate with the main app's download queue)
                self.add_to_download_queue(
                    title=track.title or track.filename,
                    artist=track.artist or album_result.artist,
                    album=album_result.album_title,
                    username=album_result.username,
                    filename=track.filename,
                    file_size=track.size,
                    download_id=download_id,
                    track_result=track
                )
            
            # Show confirmation
            QMessageBox.information(
                self, 
                "Download Started", 
                f"Started downloading {len(album_result.tracks)} tracks from '{album_result.album_title}'"
            )
            
        except Exception as e:
            print(f"Error starting album download: {e}")
            QMessageBox.critical(self, "Download Error", f"Failed to start download: {str(e)}")
    
    def add_to_download_queue(self, title, artist, album, username, filename, file_size, download_id, track_result):
        """Add a track to the download queue - needs integration with main app"""
        # TODO: This needs to integrate with the main application's download system
        # For now, we'll simulate starting the download
        
        print(f"Adding to download queue: {title} by {artist}")
        
        # We need to access the main app's download manager
        # This would typically be done by emitting a signal that the main app listens to
        # or by accessing the download manager through a parent reference
        
        # For now, just start the individual track download
        if self.soulseek_client:
            try:
                # Start the download using the soulseek client
                self.soulseek_client.download(
                    username=username,
                    filename=filename,
                    download_id=download_id
                )
                print(f"Started download: {filename}")
            except Exception as e:
                print(f"Failed to start download for {filename}: {e}")
    
    def return_to_search(self):
        """Return to search interface"""
        # Stop any running workers
        self.stop_all_workers()
        
        # Clear state
        self.selected_artist = None
        self.current_albums = []
        self.header_search_input.clear()
        
        # Clear albums display
        self.clear_albums()
        
        # Switch views
        self.artist_view.hide()
        self.search_interface.show()
    
    def stop_all_workers(self):
        """Stop all background workers"""
        if self.artist_search_worker:
            self.artist_search_worker.terminate()
            self.artist_search_worker.wait()
            self.artist_search_worker = None
            
        if self.album_fetch_worker:
            self.album_fetch_worker.terminate()
            self.album_fetch_worker.wait()
            self.album_fetch_worker = None
            
        if self.plex_library_worker:
            self.plex_library_worker.stop()
            self.plex_library_worker.terminate()
            self.plex_library_worker.wait()
            self.plex_library_worker = None
    
    def clear_artist_results(self):
        """Clear artist search results"""
        while self.artist_results_layout.count() > 0:
            item = self.artist_results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.artist_results_container.hide()
    
    def clear_albums(self):
        """Clear album display"""
        while self.albums_grid_layout.count() > 0:
            item = self.albums_grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.current_albums = []
    
    def closeEvent(self, event):
        """Handle page close/cleanup"""
        self.stop_all_workers()
        super().closeEvent(event)