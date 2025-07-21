from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                           QFrame, QPushButton, QListWidget, QListWidgetItem,
                           QProgressBar, QTextEdit, QCheckBox, QComboBox,
                           QScrollArea, QSizePolicy, QMessageBox, QDialog,
                           QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, QRunnable, QThreadPool, QObject
from PyQt6.QtGui import QFont
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class TrackAnalysisResult:
    """Result of analyzing a track for Plex existence"""
    spotify_track: object  # Spotify track object
    exists_in_plex: bool
    plex_match: Optional[object] = None  # Plex track if found
    confidence: float = 0.0
    error_message: Optional[str] = None

class PlaylistTrackAnalysisWorkerSignals(QObject):
    """Signals for playlist track analysis worker"""
    analysis_started = pyqtSignal(int)  # total_tracks
    track_analyzed = pyqtSignal(int, object)  # track_index, TrackAnalysisResult
    analysis_completed = pyqtSignal(list)  # List[TrackAnalysisResult]
    analysis_failed = pyqtSignal(str)  # error_message

class PlaylistTrackAnalysisWorker(QRunnable):
    """Background worker to analyze playlist tracks against Plex library"""
    
    def __init__(self, playlist_tracks, plex_client):
        super().__init__()
        self.playlist_tracks = playlist_tracks
        self.plex_client = plex_client
        self.signals = PlaylistTrackAnalysisWorkerSignals()
        self._cancelled = False
    
    def cancel(self):
        """Cancel the analysis operation"""
        self._cancelled = True
    
    def run(self):
        """Analyze each track in the playlist"""
        try:
            if self._cancelled:
                return
                
            self.signals.analysis_started.emit(len(self.playlist_tracks))
            results = []
            
            # Check if Plex is connected
            plex_connected = False
            try:
                if self.plex_client:
                    plex_connected = self.plex_client.is_connected()
            except Exception as e:
                print(f"Plex connection check failed: {e}")
                plex_connected = False
            
            for i, track in enumerate(self.playlist_tracks):
                if self._cancelled:
                    return
                
                result = TrackAnalysisResult(
                    spotify_track=track,
                    exists_in_plex=False
                )
                
                if plex_connected:
                    # Check if track exists in Plex
                    try:
                        plex_match, confidence = self._check_track_in_plex(track)
                        if plex_match and confidence >= 0.8:  # High confidence threshold
                            result.exists_in_plex = True
                            result.plex_match = plex_match
                            result.confidence = confidence
                    except Exception as e:
                        result.error_message = f"Plex check failed: {str(e)}"
                
                results.append(result)
                self.signals.track_analyzed.emit(i + 1, result)
            
            if not self._cancelled:
                self.signals.analysis_completed.emit(results)
                
        except Exception as e:
            if not self._cancelled:
                self.signals.analysis_failed.emit(str(e))
    
    def _check_track_in_plex(self, spotify_track):
        """Check if a Spotify track exists in Plex with confidence scoring"""
        try:
            # Search Plex for similar tracks
            # Use first artist for search
            artist_name = spotify_track.artists[0] if spotify_track.artists else ""
            search_query = f"{artist_name} {spotify_track.name}".strip()
            
            # Get potential matches from Plex
            plex_tracks = self.plex_client.search_tracks(search_query, limit=10)
            
            if not plex_tracks:
                return None, 0.0
            
            # Find best match using confidence scoring
            best_match = None
            best_confidence = 0.0
            
            for plex_track in plex_tracks:
                confidence = self._calculate_track_confidence(spotify_track, plex_track)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = plex_track
            
            return best_match, best_confidence
            
        except Exception as e:
            print(f"Error checking track in Plex: {e}")
            return None, 0.0
    
    def _calculate_track_confidence(self, spotify_track, plex_track):
        """Calculate confidence score between Spotify and Plex tracks"""
        try:
            # Basic string similarity for now (can be enhanced with existing matching engine)
            import re
            
            def normalize_string(s):
                return re.sub(r'[^a-zA-Z0-9\s]', '', s.lower()).strip()
            
            # Normalize track titles
            spotify_title = normalize_string(spotify_track.name)
            plex_title = normalize_string(plex_track.title)
            
            # Normalize artist names
            spotify_artist = normalize_string(spotify_track.artists[0]) if spotify_track.artists else ""
            plex_artist = normalize_string(plex_track.artist)
            
            # Simple similarity scoring
            title_similarity = 1.0 if spotify_title == plex_title else 0.0
            artist_similarity = 1.0 if spotify_artist == plex_artist else 0.0
            
            # Weight title more heavily
            confidence = (title_similarity * 0.7) + (artist_similarity * 0.3)
            
            # Duration check (allow 10% variance)
            if hasattr(spotify_track, 'duration_ms') and hasattr(plex_track, 'duration'):
                spotify_duration = spotify_track.duration_ms / 1000
                plex_duration = plex_track.duration / 1000 if plex_track.duration else 0
                
                if plex_duration > 0:
                    duration_diff = abs(spotify_duration - plex_duration) / max(spotify_duration, plex_duration)
                    if duration_diff <= 0.1:  # Within 10%
                        confidence += 0.1  # Bonus for duration match
            
            return min(confidence, 1.0)  # Cap at 1.0
            
        except Exception as e:
            print(f"Error calculating track confidence: {e}")
            return 0.0

class TrackDownloadWorkerSignals(QObject):
    """Signals for track download worker"""
    download_completed = pyqtSignal(int, int, str)  # download_index, track_index, download_id
    download_failed = pyqtSignal(int, int, str)  # download_index, track_index, error_message

class TrackDownloadWorker(QRunnable):
    """Background worker to download individual tracks via Soulseek"""
    
    def __init__(self, spotify_track, soulseek_client, download_index, track_index):
        super().__init__()
        self.spotify_track = spotify_track
        self.soulseek_client = soulseek_client
        self.download_index = download_index
        self.track_index = track_index
        self.signals = TrackDownloadWorkerSignals()
        self._cancelled = False
    
    def cancel(self):
        """Cancel the download operation"""
        self._cancelled = True
    
    def run(self):
        """Download the track via Soulseek"""
        try:
            if self._cancelled or not self.soulseek_client:
                return
            
            # Create search queries - try track name first, then artist + track
            track_name = self.spotify_track.name
            artist_name = self.spotify_track.artists[0] if self.spotify_track.artists else ""
            
            search_queries = []
            search_queries.append(track_name)  # Try track name only first
            if artist_name:
                search_queries.append(f"{artist_name} {track_name}")  # Then artist + track
            
            download_id = None
            
            # Try each search query until we find a download
            for query in search_queries:
                if self._cancelled:
                    return
                    
                print(f"🔍 Searching Soulseek: {query}")
                
                # Use the async method (need to run in sync context)
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    download_id = loop.run_until_complete(
                        self.soulseek_client.search_and_download_best(query)
                    )
                    if download_id:
                        break  # Success - stop trying other queries
                finally:
                    loop.close()
            
            if download_id:
                self.signals.download_completed.emit(self.download_index, self.track_index, download_id)
            else:
                self.signals.download_failed.emit(self.download_index, self.track_index, "No search results found")
                
        except Exception as e:
            self.signals.download_failed.emit(self.download_index, self.track_index, str(e))

class PlaylistLoaderThread(QThread):
    playlist_loaded = pyqtSignal(object)  # Single playlist
    loading_finished = pyqtSignal(int)  # Total count
    loading_failed = pyqtSignal(str)  # Error message
    progress_updated = pyqtSignal(str)  # Progress text
    
    def __init__(self, spotify_client):
        super().__init__()
        self.spotify_client = spotify_client
        
    def run(self):
        try:
            self.progress_updated.emit("Connecting to Spotify...")
            if not self.spotify_client or not self.spotify_client.is_authenticated():
                self.loading_failed.emit("Spotify not authenticated")
                return
            
            self.progress_updated.emit("Fetching playlists...")
            playlists = self.spotify_client.get_user_playlists_metadata_only()
            
            for i, playlist in enumerate(playlists):
                self.progress_updated.emit(f"Loading playlist {i+1}/{len(playlists)}: {playlist.name}")
                self.playlist_loaded.emit(playlist)
                self.msleep(20)  # Reduced delay for faster but visible progressive loading
            
            self.loading_finished.emit(len(playlists))
            
        except Exception as e:
            self.loading_failed.emit(str(e))

class TrackLoadingWorkerSignals(QObject):
    """Signals for async track loading worker"""
    tracks_loaded = pyqtSignal(str, list)  # playlist_id, tracks
    loading_failed = pyqtSignal(str, str)  # playlist_id, error_message
    loading_started = pyqtSignal(str)  # playlist_id

class TrackLoadingWorker(QRunnable):
    """Async worker for loading playlist tracks (following downloads.py pattern)"""
    
    def __init__(self, spotify_client, playlist_id, playlist_name):
        super().__init__()
        self.spotify_client = spotify_client
        self.playlist_id = playlist_id
        self.playlist_name = playlist_name
        self.signals = TrackLoadingWorkerSignals()
        self._cancelled = False
    
    def cancel(self):
        """Cancel the worker operation"""
        self._cancelled = True
    
    def run(self):
        """Load tracks in background thread"""
        try:
            if self._cancelled:
                return
                
            self.signals.loading_started.emit(self.playlist_id)
            
            if self._cancelled:
                return
            
            # Fetch tracks from Spotify API
            tracks = self.spotify_client._get_playlist_tracks(self.playlist_id)
            
            if self._cancelled:
                return
            
            # Emit success signal
            self.signals.tracks_loaded.emit(self.playlist_id, tracks)
            
        except Exception as e:
            if not self._cancelled:
                # Emit error signal only if not cancelled
                self.signals.loading_failed.emit(self.playlist_id, str(e))

class PlaylistDetailsModal(QDialog):
    def __init__(self, playlist, parent=None):
        super().__init__(parent)
        self.playlist = playlist
        self.parent_page = parent
        self.spotify_client = parent.spotify_client if parent else None
        
        # Thread management
        self.active_workers = []
        self.fallback_pools = []
        self.is_closing = False
        
        self.setup_ui()
        
        # Load tracks asynchronously if not already cached
        if not self.playlist.tracks and self.spotify_client:
            # Check cache first
            if hasattr(parent, 'track_cache') and playlist.id in parent.track_cache:
                self.playlist.tracks = parent.track_cache[playlist.id]
                self.refresh_track_table()
            else:
                self.load_tracks_async()
    
    def closeEvent(self, event):
        """Clean up threads and resources when modal is closed"""
        self.is_closing = True
        self.cleanup_workers()
        super().closeEvent(event)
    
    def cleanup_workers(self):
        """Clean up all active workers and thread pools"""
        # Cancel active workers first
        for worker in self.active_workers:
            try:
                if hasattr(worker, 'cancel'):
                    worker.cancel()
            except (RuntimeError, AttributeError):
                pass
        
        # Disconnect signals from active workers to prevent race conditions
        for worker in self.active_workers:
            try:
                if hasattr(worker, 'signals'):
                    # Disconnect track loading worker signals
                    try:
                        worker.signals.tracks_loaded.disconnect(self.on_tracks_loaded)
                    except (RuntimeError, TypeError):
                        pass
                    try:
                        worker.signals.loading_failed.disconnect(self.on_tracks_loading_failed)
                    except (RuntimeError, TypeError):
                        pass
                    
                    # Disconnect playlist analysis worker signals
                    try:
                        worker.signals.analysis_started.disconnect(self.on_analysis_started)
                    except (RuntimeError, TypeError):
                        pass
                    try:
                        worker.signals.track_analyzed.disconnect(self.on_track_analyzed)
                    except (RuntimeError, TypeError):
                        pass
                    try:
                        worker.signals.analysis_completed.disconnect(self.on_analysis_completed)
                    except (RuntimeError, TypeError):
                        pass
                    try:
                        worker.signals.analysis_failed.disconnect(self.on_analysis_failed)
                    except (RuntimeError, TypeError):
                        pass
            except (RuntimeError, AttributeError):
                # Signal may already be disconnected or worker deleted
                pass
        
        # Clean up fallback thread pools with timeout
        for pool in self.fallback_pools:
            try:
                pool.clear()  # Cancel pending workers
                if not pool.waitForDone(2000):  # Wait 2 seconds max
                    # Force termination if workers don't finish gracefully
                    pool.clear()
            except (RuntimeError, AttributeError):
                pass
        
        # Clear tracking lists
        self.active_workers.clear()
        self.fallback_pools.clear()
    
    def setup_ui(self):
        self.setWindowTitle(f"Playlist Details - {self.playlist.name}")
        self.setFixedSize(900, 700)
        self.setStyleSheet("""
            QDialog {
                background: #191414;
                color: #ffffff;
            }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)
        
        # Header section
        header = self.create_header()
        main_layout.addWidget(header)
        
        # Track list section
        track_list = self.create_track_list()
        main_layout.addWidget(track_list)
        
        # Button section
        button_widget = QWidget()
        button_layout = self.create_buttons()
        button_widget.setLayout(button_layout)
        main_layout.addWidget(button_widget)
    
    def create_header(self):
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: #282828;
                border-radius: 12px;
                border: 1px solid #404040;
            }
        """)
        
        layout = QVBoxLayout(header)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(10)
        
        # Playlist name
        name_label = QLabel(self.playlist.name)
        name_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        name_label.setStyleSheet("color: #ffffff; border: none; background: transparent;")
        
        # Playlist info
        info_layout = QHBoxLayout()
        info_layout.setSpacing(20)
        
        # Track count
        track_count = QLabel(f"{self.playlist.total_tracks} tracks")
        track_count.setFont(QFont("Arial", 12))
        track_count.setStyleSheet("color: #b3b3b3; border: none; background: transparent;")
        
        # Owner
        owner = QLabel(f"by {self.playlist.owner}")
        owner.setFont(QFont("Arial", 12))
        owner.setStyleSheet("color: #b3b3b3; border: none; background: transparent;")
        
        # Public/Private status
        visibility = "Public" if self.playlist.public else "Private"
        if self.playlist.collaborative:
            visibility = "Collaborative"
        status = QLabel(visibility)
        status.setFont(QFont("Arial", 12))
        status.setStyleSheet("color: #1db954; border: none; background: transparent;")
        
        info_layout.addWidget(track_count)
        info_layout.addWidget(owner)
        info_layout.addWidget(status)
        info_layout.addStretch()
        
        # Description (if available)
        if self.playlist.description:
            desc_label = QLabel(self.playlist.description)
            desc_label.setFont(QFont("Arial", 11))
            desc_label.setStyleSheet("color: #b3b3b3; border: none; background: transparent;")
            desc_label.setWordWrap(True)
            desc_label.setMaximumHeight(60)
            layout.addWidget(desc_label)
        
        layout.addWidget(name_label)
        layout.addLayout(info_layout)
        
        return header
    
    def create_track_list(self):
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background: #282828;
                border-radius: 12px;
                border: 1px solid #404040;
            }
        """)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(15)
        
        # Section title
        title = QLabel("Tracks")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff; border: none; background: transparent;")
        
        # Track table
        self.track_table = QTableWidget()
        self.track_table.setColumnCount(4)
        self.track_table.setHorizontalHeaderLabels(["Track", "Artist", "Album", "Duration"])
        
        # Set initial row count (may be 0 if tracks not loaded yet)
        track_count = len(self.playlist.tracks) if self.playlist.tracks else 1
        self.track_table.setRowCount(track_count)
        
        # Style the table
        self.track_table.setStyleSheet("""
            QTableWidget {
                background: #181818;
                border: 1px solid #404040;
                border-radius: 8px;
                gridline-color: #404040;
                color: #ffffff;
                font-size: 11px;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #333333;
            }
            QTableWidget::item:selected {
                background: #1db954;
                color: #000000;
            }
            QHeaderView::section {
                background: #404040;
                color: #ffffff;
                padding: 10px;
                border: none;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        
        # Populate table
        if self.playlist.tracks:
            for row, track in enumerate(self.playlist.tracks):
                # Track name
                track_item = QTableWidgetItem(track.name)
                track_item.setFlags(track_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.track_table.setItem(row, 0, track_item)
                
                # Artist(s)
                artists = ", ".join(track.artists)
                artist_item = QTableWidgetItem(artists)
                artist_item.setFlags(artist_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.track_table.setItem(row, 1, artist_item)
                
                # Album
                album_item = QTableWidgetItem(track.album)
                album_item.setFlags(album_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.track_table.setItem(row, 2, album_item)
                
                # Duration
                duration = self.format_duration(track.duration_ms)
                duration_item = QTableWidgetItem(duration)
                duration_item.setFlags(duration_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.track_table.setItem(row, 3, duration_item)
        else:
            # Show placeholder while tracks are being loaded
            placeholder_item = QTableWidgetItem("Tracks will load momentarily...")
            placeholder_item.setFlags(placeholder_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.track_table.setItem(0, 0, placeholder_item)
            self.track_table.setSpan(0, 0, 1, 4)
        
        # Set optimal column widths with proportional sizing
        header = self.track_table.horizontalHeader()
        header.setStretchLastSection(False)
        
        # Calculate available width (modal is 900px, account for margins/scrollbar)
        available_width = 850
        
        # Set proportional widths: Track(40%), Artist(25%), Album(25%), Duration(10%)
        track_width = int(available_width * 0.40)    # ~340px
        artist_width = int(available_width * 0.25)   # ~212px  
        album_width = int(available_width * 0.25)    # ~212px
        duration_width = 80                          # Fixed 80px
        
        # Apply column widths with interactive resize capability
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)  # Track name
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)  # Artist
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)  # Album
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)        # Duration
        
        self.track_table.setColumnWidth(0, track_width)
        self.track_table.setColumnWidth(1, artist_width)
        self.track_table.setColumnWidth(2, album_width)
        self.track_table.setColumnWidth(3, duration_width)
        
        # Set minimum widths to prevent columns from becoming too narrow
        header.setMinimumSectionSize(100)  # Minimum 100px for any column
        
        # Hide row numbers
        self.track_table.verticalHeader().setVisible(False)
        
        layout.addWidget(title)
        layout.addWidget(self.track_table)
        
        return container
    
    def create_buttons(self):
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.setFixedSize(100, 40)
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #404040;
                border: none;
                border-radius: 20px;
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #505050;
            }
        """)
        
        # Sync button
        sync_btn = QPushButton("Sync This Playlist")
        sync_btn.setFixedSize(150, 40)
        sync_btn.setStyleSheet("""
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
        
        # Download missing tracks button
        download_btn = QPushButton("Download Missing Tracks")
        download_btn.setFixedSize(180, 40)
        download_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #1db954;
                border-radius: 20px;
                color: #1db954;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(29, 185, 84, 0.1);
            }
        """)
        
        # Connect download missing tracks button
        download_btn.clicked.connect(self.on_download_missing_tracks_clicked)
        
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        button_layout.addWidget(download_btn)
        button_layout.addWidget(sync_btn)
        
        return button_layout
    
    def format_duration(self, duration_ms):
        """Convert milliseconds to MM:SS format"""
        seconds = duration_ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"
    
    def on_download_missing_tracks_clicked(self):
        """Handle Download Missing Tracks button click"""
        print("🔄 Download Missing Tracks button clicked!")
        
        if not self.playlist:
            print("❌ No playlist selected")
            QMessageBox.warning(self, "Error", "No playlist selected")
            return
            
        if not self.playlist.tracks:
            print("❌ Playlist tracks not loaded")
            QMessageBox.warning(self, "Error", "Playlist tracks not loaded")
            return
        
        print(f"✅ Playlist: {self.playlist.name} with {len(self.playlist.tracks)} tracks")
        
        # Get access to parent's Plex and Soulseek clients through parent reference
        if not hasattr(self.parent_page, 'plex_client'):
            print("❌ Plex client not available")
            QMessageBox.warning(self, "Service Unavailable", 
                              "Plex client not available. Please check your configuration.")
            return
        
        print("✅ Plex client available")
            
        # Create and show the enhanced download missing tracks modal
        try:
            print("🚀 Creating modal...")
            modal = DownloadMissingTracksModal(self.playlist, self.parent_page, self)
            print("✅ Modal created successfully")
            
            # Store modal reference to prevent garbage collection
            self.download_modal = modal
            
            print("🖥️ Closing current sync modal...")
            self.accept()  # Close the current sync modal
            
            print("🖥️ Showing download modal...")
            result = modal.exec()
            print(f"✅ Modal closed with result: {result}")
            
        except Exception as e:
            print(f"❌ Exception creating modal: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Modal Error", f"Failed to open download modal: {str(e)}")
    
    def start_playlist_missing_tracks_download(self):
        """Start the process of downloading missing tracks from playlist"""
        track_count = len(self.playlist.tracks)
        
        # Start analysis worker
        self.start_track_analysis()
        
        # Show analysis started message
        QMessageBox.information(self, "Analysis Started", 
                              f"Starting analysis of {track_count} tracks.\nChecking Plex library for existing tracks...")
    
    def start_track_analysis(self):
        """Start background track analysis against Plex library"""
        # Create analysis worker
        plex_client = getattr(self.parent_page, 'plex_client', None)
        worker = PlaylistTrackAnalysisWorker(self.playlist.tracks, plex_client)
        
        # Connect signals
        worker.signals.analysis_started.connect(self.on_analysis_started)
        worker.signals.track_analyzed.connect(self.on_track_analyzed)
        worker.signals.analysis_completed.connect(self.on_analysis_completed)
        worker.signals.analysis_failed.connect(self.on_analysis_failed)
        
        # Track worker for cleanup
        self.active_workers.append(worker)
        
        # Submit to thread pool
        if hasattr(self.parent_page, 'thread_pool'):
            self.parent_page.thread_pool.start(worker)
        else:
            # Create and track fallback thread pool
            thread_pool = QThreadPool()
            self.fallback_pools.append(thread_pool)
            thread_pool.start(worker)
    
    def on_analysis_started(self, total_tracks):
        """Handle analysis started signal"""
        print(f"Started analyzing {total_tracks} tracks against Plex library")
    
    def on_track_analyzed(self, track_index, result):
        """Handle individual track analysis completion"""
        track = result.spotify_track
        if result.exists_in_plex:
            print(f"Track {track_index}: '{track.name}' by {track.artists[0]} EXISTS in Plex (confidence: {result.confidence:.2f})")
        else:
            print(f"Track {track_index}: '{track.name}' by {track.artists[0]} MISSING from Plex - will download")
    
    def on_analysis_completed(self, results):
        """Handle analysis completion and start downloads for missing tracks"""
        missing_tracks = [r for r in results if not r.exists_in_plex]
        existing_tracks = [r for r in results if r.exists_in_plex]
        
        print(f"Analysis complete: {len(missing_tracks)} missing, {len(existing_tracks)} existing")
        
        if not missing_tracks:
            QMessageBox.information(self, "Analysis Complete", 
                                  "All tracks already exist in Plex library!\nNo downloads needed.")
            return
        
        # Show results to user
        message = f"Analysis complete!\n\n"
        message += f"Tracks already in Plex: {len(existing_tracks)}\n"
        message += f"Tracks to download: {len(missing_tracks)}\n\n"
        message += "Ready to start downloading missing tracks?"
        
        reply = QMessageBox.question(self, "Start Downloads?", message,
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.start_missing_track_downloads(missing_tracks)
    
    def on_analysis_failed(self, error_message):
        """Handle analysis failure"""
        QMessageBox.critical(self, "Analysis Failed", f"Failed to analyze tracks: {error_message}")
    
    def start_missing_track_downloads(self, missing_tracks):
        """Start downloading the missing tracks"""
        # TODO: Implement Soulseek search and download queueing
        # For now, just show what would be downloaded
        track_list = []
        for result in missing_tracks:
            track = result.spotify_track
            artist = track.artists[0] if track.artists else "Unknown Artist"
            track_list.append(f"• {track.name} by {artist}")
        
        message = f"Would download {len(missing_tracks)} tracks:\n\n"
        message += "\n".join(track_list[:10])  # Show first 10
        if len(track_list) > 10:
            message += f"\n... and {len(track_list) - 10} more"
        
        QMessageBox.information(self, "Downloads Queued", message)
    
    def load_tracks_async(self):
        """Load tracks asynchronously using worker thread"""
        if not self.spotify_client:
            return
        
        # Show loading state in track table
        if hasattr(self, 'track_table'):
            self.track_table.setRowCount(1)
            loading_item = QTableWidgetItem("Loading tracks...")
            loading_item.setFlags(loading_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.track_table.setItem(0, 0, loading_item)
            self.track_table.setSpan(0, 0, 1, 4)
        
        # Create and submit worker to thread pool
        worker = TrackLoadingWorker(self.spotify_client, self.playlist.id, self.playlist.name)
        worker.signals.tracks_loaded.connect(self.on_tracks_loaded)
        worker.signals.loading_failed.connect(self.on_tracks_loading_failed)
        
        # Track active worker for cleanup
        self.active_workers.append(worker)
        
        # Submit to parent's thread pool if available, otherwise create one
        if hasattr(self.parent_page, 'thread_pool'):
            self.parent_page.thread_pool.start(worker)
        else:
            # Create and track fallback thread pool
            thread_pool = QThreadPool()
            self.fallback_pools.append(thread_pool)
            thread_pool.start(worker)
    
    def on_tracks_loaded(self, playlist_id, tracks):
        """Handle successful track loading"""
        # Validate modal state before processing
        if (playlist_id == self.playlist.id and 
            not self.is_closing and 
            not self.isHidden() and 
            hasattr(self, 'track_table')):
            
            self.playlist.tracks = tracks
            
            # Cache tracks in parent for future use
            if hasattr(self.parent_page, 'track_cache'):
                self.parent_page.track_cache[playlist_id] = tracks
            
            # Refresh the track table
            self.refresh_track_table()
    
    def on_tracks_loading_failed(self, playlist_id, error_message):
        """Handle track loading failure"""
        # Validate modal state before processing
        if (playlist_id == self.playlist.id and 
            not self.is_closing and 
            not self.isHidden() and 
            hasattr(self, 'track_table')):
            self.track_table.setRowCount(1)
            error_item = QTableWidgetItem(f"Error loading tracks: {error_message}")
            error_item.setFlags(error_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.track_table.setItem(0, 0, error_item)
            self.track_table.setSpan(0, 0, 1, 4)
    
    def refresh_track_table(self):
        """Refresh the track table with loaded tracks"""
        if not hasattr(self, 'track_table'):
            return
            
        self.track_table.setRowCount(len(self.playlist.tracks))
        self.track_table.clearSpans()  # Remove any spans from loading state
        
        # Populate table
        for row, track in enumerate(self.playlist.tracks):
            # Track name
            track_item = QTableWidgetItem(track.name)
            track_item.setFlags(track_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.track_table.setItem(row, 0, track_item)
            
            # Artist(s)
            artists = ", ".join(track.artists)
            artist_item = QTableWidgetItem(artists)
            artist_item.setFlags(artist_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.track_table.setItem(row, 1, artist_item)
            
            # Album
            album_item = QTableWidgetItem(track.album)
            album_item.setFlags(album_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.track_table.setItem(row, 2, album_item)
            
            # Duration
            duration = self.format_duration(track.duration_ms)
            duration_item = QTableWidgetItem(duration)
            duration_item.setFlags(duration_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.track_table.setItem(row, 3, duration_item)

class PlaylistItem(QFrame):
    view_details_clicked = pyqtSignal(object)  # Signal to emit playlist object
    
    def __init__(self, name: str, track_count: int, sync_status: str, playlist=None, parent=None):
        super().__init__(parent)
        self.name = name
        self.track_count = track_count
        self.sync_status = sync_status
        self.playlist = playlist  # Store playlist object reference
        self.is_selected = False
        self.setup_ui()
    
    def setup_ui(self):
        self.setFixedHeight(80)
        self.setStyleSheet("""
            PlaylistItem {
                background: #282828;
                border-radius: 8px;
                border: 1px solid #404040;
            }
            PlaylistItem:hover {
                background: #333333;
                border: 1px solid #1db954;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(15)
        
        # Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setStyleSheet("""
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 9px;
                border: 2px solid #b3b3b3;
                background: transparent;
            }
            QCheckBox::indicator:checked {
                background: #1db954;
                border: 2px solid #1db954;
            }
            QCheckBox::indicator:checked:hover {
                background: #1ed760;
            }
        """)
        
        # Content layout
        content_layout = QVBoxLayout()
        content_layout.setSpacing(5)
        
        # Playlist name
        name_label = QLabel(self.name)
        name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        name_label.setStyleSheet("color: #ffffff;")
        
        # Track count and status
        info_layout = QHBoxLayout()
        info_layout.setSpacing(20)
        
        track_label = QLabel(f"{self.track_count} tracks")
        track_label.setFont(QFont("Arial", 10))
        track_label.setStyleSheet("color: #b3b3b3;")
        
        status_label = QLabel(self.sync_status)
        status_label.setFont(QFont("Arial", 10))
        if self.sync_status == "Synced":
            status_label.setStyleSheet("color: #1db954;")
        elif self.sync_status == "Needs Sync":
            status_label.setStyleSheet("color: #ffa500;")
        else:
            status_label.setStyleSheet("color: #e22134;")
        
        info_layout.addWidget(track_label)
        info_layout.addWidget(status_label)
        info_layout.addStretch()
        
        content_layout.addWidget(name_label)
        content_layout.addLayout(info_layout)
        
        # Action button
        action_btn = QPushButton("Sync / Download")
        action_btn.setFixedSize(120, 30)  # Slightly wider for longer text
        action_btn.clicked.connect(self.on_view_details_clicked)
        action_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #1db954;
                border-radius: 15px;
                color: #1db954;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #1db954;
                color: #000000;
            }
        """)
        
        layout.addWidget(self.checkbox)
        layout.addLayout(content_layout)
        layout.addStretch()
        layout.addWidget(action_btn)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.checkbox.setChecked(not self.checkbox.isChecked())
        super().mousePressEvent(event)
    
    def on_view_details_clicked(self):
        """Handle View Details button click"""
        if self.playlist:
            self.view_details_clicked.emit(self.playlist)

class SyncOptionsPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet("""
            SyncOptionsPanel {
                background: #282828;
                border-radius: 8px;
                border: 1px solid #404040;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title_label = QLabel("Sync Options")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #ffffff;")
        
        # Download missing tracks option
        self.download_missing = QCheckBox("Download missing tracks from Soulseek")
        self.download_missing.setChecked(True)
        self.download_missing.setStyleSheet("""
            QCheckBox {
                color: #ffffff;
                font-size: 11px;
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
        """)
        
        # Quality selection
        quality_layout = QHBoxLayout()
        quality_label = QLabel("Preferred Quality:")
        quality_label.setStyleSheet("color: #b3b3b3; font-size: 11px;")
        
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["FLAC", "320 kbps MP3", "256 kbps MP3", "Any"])
        self.quality_combo.setCurrentText("FLAC")
        self.quality_combo.setStyleSheet("""
            QComboBox {
                background: #404040;
                border: 1px solid #606060;
                border-radius: 4px;
                padding: 5px;
                color: #ffffff;
                font-size: 11px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border: none;
            }
        """)
        
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality_combo)
        quality_layout.addStretch()
        
        layout.addWidget(title_label)
        layout.addWidget(self.download_missing)
        layout.addLayout(quality_layout)

class SyncPage(QWidget):
    def __init__(self, spotify_client=None, plex_client=None, parent=None):
        super().__init__(parent)
        self.spotify_client = spotify_client
        self.plex_client = plex_client
        self.current_playlists = []
        self.playlist_loader = None
        
        # Track cache for performance
        self.track_cache = {}  # playlist_id -> tracks
        
        # Thread pool for async operations (like downloads.py)
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(3)  # Limit concurrent Spotify API calls
        
        self.setup_ui()
        
        # Don't auto-load on startup, but do auto-load when page becomes visible
        self.show_initial_state()
        self.playlists_loaded = False
    
    def showEvent(self, event):
        """Auto-load playlists when page becomes visible (but not during app startup)"""
        super().showEvent(event)
        
        # Only auto-load once and only if we have a spotify client
        if (not self.playlists_loaded and 
            self.spotify_client and 
            self.spotify_client.is_authenticated()):
            
            # Small delay to ensure UI is fully rendered
            QTimer.singleShot(100, self.auto_load_playlists)
    
    def auto_load_playlists(self):
        """Auto-load playlists with proper UI transition"""
        # Clear the welcome state first
        self.clear_playlists()
        
        # Start loading (this will set playlists_loaded = True)
        self.load_playlists_async()
    
    def show_initial_state(self):
        """Show initial state with option to load playlists"""
        # Add welcome message to playlist area
        welcome_message = QLabel("Ready to sync playlists!\nClick 'Load Playlists' to get started.")
        welcome_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_message.setStyleSheet("""
            QLabel {
                color: #b3b3b3;
                font-size: 16px;
                padding: 60px;
                background: #282828;
                border-radius: 12px;
                border: 1px solid #404040;
                line-height: 1.5;
            }
        """)
        
        # Add load button
        load_btn = QPushButton("🎵 Load Playlists")
        load_btn.setFixedSize(200, 50)
        load_btn.clicked.connect(self.load_playlists_async)
        load_btn.setStyleSheet("""
            QPushButton {
                background: #1db954;
                border: none;
                border-radius: 25px;
                color: #000000;
                font-size: 14px;
                font-weight: bold;
                margin-top: 20px;
            }
            QPushButton:hover {
                background: #1ed760;
            }
        """)
        
        # Add them to the playlist layout  
        if hasattr(self, 'playlist_layout'):
            self.playlist_layout.addWidget(welcome_message)
            self.playlist_layout.addWidget(load_btn)
            self.playlist_layout.addStretch()
    
    def setup_ui(self):
        self.setStyleSheet("""
            SyncPage {
                background: #191414;
            }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(25)
        
        # Header
        header = self.create_header()
        main_layout.addWidget(header)
        
        # Content area
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)  # Reduced from 25 to 15 for tighter spacing
        
        # Left side - Playlist list
        playlist_section = self.create_playlist_section()
        content_layout.addWidget(playlist_section, 2)
        
        # Right side - Options and actions
        right_sidebar = self.create_right_sidebar()
        content_layout.addWidget(right_sidebar, 1)
        
        main_layout.addLayout(content_layout, 1)  # Allow content to stretch
    
    def create_header(self):
        header = QWidget()
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Title
        title_label = QLabel("Playlist Sync")
        title_label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #ffffff;")
        
        # Subtitle
        subtitle_label = QLabel("Synchronize your Spotify playlists with Plex")
        subtitle_label.setFont(QFont("Arial", 14))
        subtitle_label.setStyleSheet("color: #b3b3b3;")
        
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        
        return header
    
    def create_playlist_section(self):
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setSpacing(15)
        
        # Section header
        header_layout = QHBoxLayout()
        
        section_title = QLabel("Spotify Playlists")
        section_title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        section_title.setStyleSheet("color: #ffffff;")
        
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.setFixedSize(100, 35)
        self.refresh_btn.clicked.connect(self.load_playlists_async)
        self.refresh_btn.setStyleSheet("""
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
            QPushButton:pressed {
                background: #1aa34a;
            }
        """)
        
        header_layout.addWidget(section_title)
        header_layout.addStretch()
        header_layout.addWidget(self.refresh_btn)
        
        # Playlist container
        playlist_container = QScrollArea()
        playlist_container.setWidgetResizable(True)
        playlist_container.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #282828;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #1db954;
                border-radius: 4px;
            }
        """)
        
        self.playlist_widget = QWidget()
        self.playlist_layout = QVBoxLayout(self.playlist_widget)
        self.playlist_layout.setSpacing(10)
        
        # Playlists will be loaded asynchronously after UI setup
        
        self.playlist_layout.addStretch()
        playlist_container.setWidget(self.playlist_widget)
        
        layout.addLayout(header_layout)
        layout.addWidget(playlist_container)
        
        return section
    
    def create_right_sidebar(self):
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setSpacing(20)
        
        # Sync options
        options_panel = SyncOptionsPanel()
        layout.addWidget(options_panel)
        
        # Action buttons
        actions_frame = QFrame()
        actions_frame.setStyleSheet("""
            QFrame {
                background: #282828;
                border-radius: 8px;
                border: 1px solid #404040;
            }
        """)
        
        actions_layout = QVBoxLayout(actions_frame)
        actions_layout.setContentsMargins(20, 20, 20, 20)
        actions_layout.setSpacing(15)
        
        # Sync button
        sync_btn = QPushButton("Start Sync")
        sync_btn.setFixedHeight(45)
        sync_btn.setStyleSheet("""
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
            QPushButton:pressed {
                background: #1aa34a;
            }
        """)
        
        # Preview button
        preview_btn = QPushButton("Preview Changes")
        preview_btn.setFixedHeight(35)
        preview_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #1db954;
                border-radius: 17px;
                color: #1db954;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(29, 185, 84, 0.1);
            }
        """)
        
        actions_layout.addWidget(sync_btn)
        actions_layout.addWidget(preview_btn)
        
        layout.addWidget(actions_frame)
        
        # Progress section below buttons
        progress_section = self.create_progress_section()
        layout.addWidget(progress_section, 1)  # Allow progress section to stretch
        
        return section
    
    def create_progress_section(self):
        section = QFrame()
        section.setMinimumHeight(200)  # Set minimum height instead of fixed
        section.setStyleSheet("""
            QFrame {
                background: #282828;
                border-radius: 8px;
                border: 1px solid #404040;
            }
        """)
        
        layout = QVBoxLayout(section)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(10)
        
        # Progress header
        progress_header = QLabel("Sync Progress")
        progress_header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        progress_header.setStyleSheet("color: #ffffff;")
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                background: #404040;
            }
            QProgressBar::chunk {
                background: #1db954;
                border-radius: 4px;
            }
        """)
        
        # Progress text
        self.progress_text = QLabel("Ready to sync...")
        self.progress_text.setFont(QFont("Arial", 11))
        self.progress_text.setStyleSheet("color: #b3b3b3;")
        
        # Log area
        self.log_area = QTextEdit()
        self.log_area.setMinimumHeight(80)  # Set minimum height instead of maximum
        self.log_area.setStyleSheet("""
            QTextEdit {
                background: #181818;
                border: 1px solid #404040;
                border-radius: 4px;
                color: #ffffff;
                font-size: 10px;
                font-family: monospace;
            }
        """)
        self.log_area.setPlainText("Waiting for sync to start...")
        
        layout.addWidget(progress_header)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.progress_text)
        layout.addWidget(self.log_area, 1)  # Allow log area to stretch
        
        return section
    
    def load_playlists_async(self):
        """Start asynchronous playlist loading"""
        if self.playlist_loader and self.playlist_loader.isRunning():
            return
        
        # Mark as loaded to prevent duplicate auto-loading
        self.playlists_loaded = True
        
        # Clear existing playlists
        self.clear_playlists()
        
        # Add loading placeholder
        loading_label = QLabel("🔄 Loading playlists...")
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_label.setStyleSheet("""
            QLabel {
                color: #b3b3b3;
                font-size: 14px;
                padding: 40px;
                background: #282828;
                border-radius: 8px;
                border: 1px solid #404040;
            }
        """)
        self.playlist_layout.insertWidget(0, loading_label)
        
        # Show loading state
        self.refresh_btn.setText("🔄 Loading...")
        self.refresh_btn.setEnabled(False)
        self.log_area.append("Starting playlist loading...")
        
        # Create and start loader thread
        self.playlist_loader = PlaylistLoaderThread(self.spotify_client)
        self.playlist_loader.playlist_loaded.connect(self.add_playlist_to_ui)
        self.playlist_loader.loading_finished.connect(self.on_loading_finished)
        self.playlist_loader.loading_failed.connect(self.on_loading_failed)
        self.playlist_loader.progress_updated.connect(self.update_progress)
        self.playlist_loader.start()
    
    def add_playlist_to_ui(self, playlist):
        """Add a single playlist to the UI as it's loaded"""
        # Simple sync status (placeholder for now)
        sync_status = "Never Synced"  # TODO: Check actual sync status
        item = PlaylistItem(playlist.name, playlist.total_tracks, sync_status, playlist)
        item.view_details_clicked.connect(self.show_playlist_details)
        
        # Add subtle fade-in animation
        item.setStyleSheet(item.styleSheet() + "background: rgba(40, 40, 40, 0);")
        
        # Insert before the stretch item
        self.playlist_layout.insertWidget(self.playlist_layout.count() - 1, item)
        self.current_playlists.append(playlist)
        
        # Animate the item appearing
        self.animate_item_fade_in(item)
        
        # Update log
        self.log_area.append(f"Added playlist: {playlist.name} ({playlist.total_tracks} tracks)")
    
    def animate_item_fade_in(self, item):
        """Add a subtle fade-in animation to playlist items"""
        # Start with reduced opacity
        item.setStyleSheet("""
            PlaylistItem {
                background: #282828;
                border-radius: 8px;
                border: 1px solid #404040;
                opacity: 0.3;
            }
            PlaylistItem:hover {
                background: #333333;
                border: 1px solid #1db954;
            }
        """)
        
        # Animate to full opacity after a short delay
        QTimer.singleShot(50, lambda: item.setStyleSheet("""
            PlaylistItem {
                background: #282828;
                border-radius: 8px;
                border: 1px solid #404040;
            }
            PlaylistItem:hover {
                background: #333333;
                border: 1px solid #1db954;
            }
        """))
    
    def on_loading_finished(self, count):
        """Handle completion of playlist loading"""
        # Remove loading placeholder if it exists
        for i in range(self.playlist_layout.count()):
            item = self.playlist_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), QLabel):
                if "Loading playlists" in item.widget().text():
                    item.widget().deleteLater()
                    break
        
        self.refresh_btn.setText("🔄 Refresh")
        self.refresh_btn.setEnabled(True)
        self.log_area.append(f"✓ Loaded {count} Spotify playlists successfully")
        
        # Start background preloading of tracks for smaller playlists
        self.start_background_preloading()
    
    def start_background_preloading(self):
        """Start background preloading of tracks for smaller playlists"""
        if not self.spotify_client:
            return
        
        # Preload tracks for playlists with < 100 tracks to improve responsiveness
        for playlist in self.current_playlists:
            if (playlist.total_tracks < 100 and 
                playlist.id not in self.track_cache and 
                not playlist.tracks):
                
                # Create background worker
                worker = TrackLoadingWorker(self.spotify_client, playlist.id, playlist.name)
                worker.signals.tracks_loaded.connect(self.on_background_tracks_loaded)
                # Don't connect error signals for background loading to avoid spam
                
                # Submit with low priority
                self.thread_pool.start(worker)
                
                # Add delay between requests to be nice to Spotify API
                QTimer.singleShot(2000, lambda: None)  # 2 second delay
    
    def on_background_tracks_loaded(self, playlist_id, tracks):
        """Handle background track loading completion"""
        # Cache the tracks for future use
        self.track_cache[playlist_id] = tracks
        
        # Update the playlist object if we can find it
        for playlist in self.current_playlists:
            if playlist.id == playlist_id:
                playlist.tracks = tracks
                break
        
    def on_loading_failed(self, error_msg):
        """Handle playlist loading failure"""
        # Remove loading placeholder if it exists
        for i in range(self.playlist_layout.count()):
            item = self.playlist_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), QLabel):
                if "Loading playlists" in item.widget().text():
                    item.widget().deleteLater()
                    break
        
        self.refresh_btn.setText("🔄 Refresh")
        self.refresh_btn.setEnabled(True)
        self.log_area.append(f"✗ Failed to load playlists: {error_msg}")
        QMessageBox.critical(self, "Error", f"Failed to load playlists: {error_msg}")
    
    def update_progress(self, message):
        """Update progress text"""
        self.log_area.append(message)
    
    def load_initial_playlists(self):
        """Load initial playlist data (placeholder or real)"""
        if self.spotify_client and self.spotify_client.is_authenticated():
            self.refresh_playlists()
        else:
            # Show placeholder playlists
            playlists = [
                ("Liked Songs", 247, "Synced"),
                ("Discover Weekly", 30, "Needs Sync"),
                ("Chill Vibes", 89, "Synced"),
                ("Workout Mix", 156, "Needs Sync"),
                ("Road Trip", 67, "Never Synced"),
                ("Focus Music", 45, "Synced")
            ]
            
            for name, count, status in playlists:
                item = PlaylistItem(name, count, status, None)  # No playlist object for placeholders
                self.playlist_layout.addWidget(item)
    
    def refresh_playlists(self):
        """Refresh playlists from Spotify API using async loader"""
        if not self.spotify_client:
            QMessageBox.warning(self, "Error", "Spotify client not available")
            return
        
        if not self.spotify_client.is_authenticated():
            QMessageBox.warning(self, "Error", "Spotify not authenticated. Please check your settings.")
            return
        
        # Use the async loader
        self.load_playlists_async()
    
    def show_playlist_details(self, playlist):
        """Show playlist details modal"""
        if playlist:
            modal = PlaylistDetailsModal(playlist, self)
            modal.exec()
    
    def clear_playlists(self):
        """Clear all playlist items from the layout"""
        # Clear the current playlists list
        self.current_playlists = []
        
        # Remove all items including welcome state
        for i in reversed(range(self.playlist_layout.count())):
            item = self.playlist_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
            elif item.spacerItem():
                continue  # Keep the stretch spacer
            else:
                self.playlist_layout.removeItem(item)
    
    def create_download_progress_bubble(self, progress_info):
        """Create a progress bubble for ongoing downloads"""
        if hasattr(self, 'progress_bubble'):
            # Remove existing bubble
            self.progress_bubble.deleteLater()
        
        # Create bubble widget
        self.progress_bubble = QFrame(self)
        self.progress_bubble.setFixedSize(300, 80)
        self.progress_bubble.setStyleSheet("""
            QFrame {
                background-color: #1db954;
                border: 2px solid #169441;
                border-radius: 15px;
                color: #000000;
            }
            QLabel {
                color: #000000;
                font-weight: bold;
            }
        """)
        
        # Create bubble layout
        bubble_layout = QVBoxLayout(self.progress_bubble)
        bubble_layout.setContentsMargins(10, 8, 10, 8)
        bubble_layout.setSpacing(5)
        
        # Title
        title = QLabel(f"📥 {progress_info['playlist_name']}")
        title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        
        # Progress text
        if progress_info['analysis_complete']:
            progress_text = f"Downloading: {progress_info['download_progress']}/{progress_info['download_total']}"
        else:
            progress_text = f"Analyzing: {progress_info['analysis_progress']}/{progress_info['total_tracks']}"
        
        progress_label = QLabel(progress_text)
        progress_label.setFont(QFont("Arial", 9))
        
        # Click to reopen
        click_label = QLabel("Click to view details")
        click_label.setFont(QFont("Arial", 8))
        click_label.setStyleSheet("color: #666666;")
        
        bubble_layout.addWidget(title)
        bubble_layout.addWidget(progress_label)
        bubble_layout.addWidget(click_label)
        
        # Position bubble in top-right corner
        self.progress_bubble.move(self.width() - 320, 20)
        self.progress_bubble.show()
        
        # Make bubble clickable
        self.progress_bubble.mousePressEvent = lambda event: self.reopen_download_modal(progress_info['modal_reference'])
        
        # Store reference for updates
        self.progress_bubble.progress_info = progress_info
    
    def reopen_download_modal(self, modal_reference):
        """Reopen the download modal from the progress bubble"""
        if modal_reference and not modal_reference.isVisible():
            # Remove bubble
            if hasattr(self, 'progress_bubble'):
                self.progress_bubble.deleteLater()
                delattr(self, 'progress_bubble')
            
            # Show modal
            modal_reference.show()
            modal_reference.activateWindow()
            modal_reference.raise_()


class DownloadMissingTracksModal(QDialog):
    """Enhanced modal for downloading missing tracks with live progress tracking"""
    
    def __init__(self, playlist, parent_page, sync_modal):
        print(f"🏗️ Initializing DownloadMissingTracksModal...")
        super().__init__(sync_modal)  # Set sync modal as parent
        self.playlist = playlist
        self.parent_page = parent_page
        self.sync_modal = sync_modal
        
        # State tracking
        self.total_tracks = len(playlist.tracks)
        self.matched_tracks_count = 0
        self.tracks_to_download_count = 0
        self.analysis_complete = False
        self.download_in_progress = False
        
        print(f"📊 Total tracks: {self.total_tracks}")
        
        # Track analysis results
        self.analysis_results = []
        self.missing_tracks = []
        
        # Worker tracking
        self.active_workers = []
        self.fallback_pools = []
        
        print("🎨 Setting up UI...")
        self.setup_ui()
        print("✅ Modal initialization complete")
        
    def setup_ui(self):
        """Set up the enhanced modal UI"""
        self.setWindowTitle(f"Download Missing Tracks - {self.playlist.name}")
        self.resize(1200, 900)  # Larger size
        self.setModal(True)
        
        # Set window flags for proper dialog behavior
        self.setWindowFlags(Qt.WindowType.Dialog)
        
        # Improved dark theme styling
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QPushButton {
                background-color: #1db954;
                color: #000000;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                padding: 10px 20px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #1ed760;
            }
            QPushButton:disabled {
                background-color: #404040;
                color: #888888;
            }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(15)
        
        # Compact header with dashboard in same row
        top_section = self.create_compact_top_section()
        main_layout.addWidget(top_section)
        
        # Progress bars section (compact)
        progress_section = self.create_progress_section()
        main_layout.addWidget(progress_section)
        
        # Track table (main focus - takes most space)
        table_section = self.create_track_table()
        main_layout.addWidget(table_section, stretch=1)  # Give it all available space
        
        # Button controls
        button_section = self.create_buttons()
        main_layout.addWidget(button_section)
        
    def create_compact_top_section(self):
        """Create compact top section with header and dashboard combined"""
        top_frame = QFrame()
        top_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #444444;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        
        layout = QVBoxLayout(top_frame)
        layout.setSpacing(15)
        
        # Header row
        header_layout = QHBoxLayout()
        
        # Left side - Title and subtitle
        title_section = QVBoxLayout()
        title_section.setSpacing(2)
        
        title = QLabel("Download Missing Tracks")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #1db954;")
        
        subtitle = QLabel(f"Playlist: {self.playlist.name}")
        subtitle.setFont(QFont("Arial", 11))
        subtitle.setStyleSheet("color: #aaaaaa;")
        
        title_section.addWidget(title)
        title_section.addWidget(subtitle)
        
        # Right side - Dashboard counters (horizontal)
        dashboard_layout = QHBoxLayout()
        dashboard_layout.setSpacing(20)
        
        # Total Tracks
        self.total_card = self.create_compact_counter_card("📀 Total", str(self.total_tracks), "#1db954")
        
        # Matched Tracks
        self.matched_card = self.create_compact_counter_card("✅ Found", "0", "#4CAF50")
        
        # To Download
        self.download_card = self.create_compact_counter_card("⬇️ Missing", "0", "#ff6b6b")
        
        dashboard_layout.addWidget(self.total_card)
        dashboard_layout.addWidget(self.matched_card)
        dashboard_layout.addWidget(self.download_card)
        dashboard_layout.addStretch()
        
        header_layout.addLayout(title_section)
        header_layout.addStretch()
        header_layout.addLayout(dashboard_layout)
        
        layout.addLayout(header_layout)
        
        return top_frame
        
    def create_dashboard(self):
        """Create dashboard with live counters"""
        dashboard_frame = QFrame()
        dashboard_frame.setStyleSheet("""
            QFrame {
                background-color: #404040;
                border: 1px solid #555555;
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 5px;
            }
        """)
        
        layout = QHBoxLayout(dashboard_frame)
        layout.setSpacing(30)
        
        # Total Tracks
        self.total_card = self.create_counter_card("📀 Total Tracks", str(self.total_tracks), "#1db954")
        
        # Matched Tracks
        self.matched_card = self.create_counter_card("✅ Matched", "0", "#1ed760")
        
        # To Download
        self.download_card = self.create_counter_card("⬇️ To Download", "0", "#ff6b6b")
        
        layout.addWidget(self.total_card)
        layout.addWidget(self.matched_card)
        layout.addWidget(self.download_card)
        layout.addStretch()
        
        return dashboard_frame
        
    def create_compact_counter_card(self, title, count, color):
        """Create a compact counter card widget"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #3a3a3a;
                border: 2px solid {color};
                border-radius: 6px;
                padding: 8px 12px;
                min-width: 80px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        count_label = QLabel(count)
        count_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        count_label.setStyleSheet(f"color: {color}; background: transparent;")
        count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 9))
        title_label.setStyleSheet("color: #cccccc; background: transparent;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(count_label)
        layout.addWidget(title_label)
        
        # Store references for updates
        if "Total" in title:
            self.total_count_label = count_label
        elif "Found" in title:
            self.matched_count_label = count_label
        elif "Missing" in title:
            self.download_count_label = count_label
            
        return card
        
    def create_counter_card(self, title, count, color):
        """Create a counter card widget"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #333333;
                border: 2px solid {color};
                border-radius: 6px;
                padding: 10px;
                min-width: 120px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(5)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 10))
        title_label.setStyleSheet("color: #b3b3b3;")
        
        count_label = QLabel(count)
        count_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        count_label.setStyleSheet(f"color: {color};")
        count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(title_label)
        layout.addWidget(count_label)
        
        # Store references for updates
        if "Total" in title:
            self.total_count_label = count_label
        elif "Matched" in title:
            self.matched_count_label = count_label
        elif "Download" in title:
            self.download_count_label = count_label
            
        return card
        
    def create_progress_section(self):
        """Create compact dual progress bar section"""
        progress_frame = QFrame()
        progress_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #444444;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        
        layout = QVBoxLayout(progress_frame)
        layout.setSpacing(8)
        
        # Plex Analysis Progress
        analysis_container = QVBoxLayout()
        analysis_container.setSpacing(4)
        
        analysis_label = QLabel("🔍 Plex Analysis")
        analysis_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        analysis_label.setStyleSheet("color: #cccccc;")
        
        self.analysis_progress = QProgressBar()
        self.analysis_progress.setFixedHeight(20)
        self.analysis_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 10px;
                text-align: center;
                background-color: #444444;
                color: #ffffff;
                font-size: 11px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #1db954;
                border-radius: 9px;
            }
        """)
        self.analysis_progress.setVisible(False)
        
        analysis_container.addWidget(analysis_label)
        analysis_container.addWidget(self.analysis_progress)
        
        # Download Progress
        download_container = QVBoxLayout()
        download_container.setSpacing(4)
        
        download_label = QLabel("⬇️ Download Progress")
        download_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        download_label.setStyleSheet("color: #cccccc;")
        
        self.download_progress = QProgressBar()
        self.download_progress.setFixedHeight(20)
        self.download_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 10px;
                text-align: center;
                background-color: #444444;
                color: #ffffff;
                font-size: 11px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #ff6b6b;
                border-radius: 9px;
            }
        """)
        self.download_progress.setVisible(False)
        
        download_container.addWidget(download_label)
        download_container.addWidget(self.download_progress)
        
        layout.addLayout(analysis_container)
        layout.addLayout(download_container)
        
        return progress_frame
        
    def create_track_table(self):
        """Create enhanced track table with Matched/Downloaded columns"""
        table_frame = QFrame()
        table_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #444444;
                border-radius: 8px;
                padding: 0px;
            }
        """)
        
        layout = QVBoxLayout(table_frame)
        layout.setContentsMargins(15, 15, 15, 15)  # Internal padding for spacing
        layout.setSpacing(10)
        
        # Table header
        header_label = QLabel("📋 Track Analysis")
        header_label.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        header_label.setStyleSheet("color: #ffffff; padding: 5px;")
        
        # Create custom header row instead of table header
        custom_header = self.create_custom_header()
        
        # Create table WITHOUT header
        self.track_table = QTableWidget()
        self.track_table.setColumnCount(5)
        self.track_table.horizontalHeader().setVisible(False)  # Hide the problematic header
        
        # Clean table styling (no header needed now)
        self.track_table.setStyleSheet("""
            QTableWidget {
                background-color: #3a3a3a;
                alternate-background-color: #424242;
                selection-background-color: #1db954;
                selection-color: #000000;
                gridline-color: #555555;
                color: #ffffff;
                border: 1px solid #555555;
                border-top: none;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 12px 8px;
                border-bottom: 1px solid #4a4a4a;
            }
            QTableWidget::item:selected {
                background-color: #1db954;
                color: #000000;
            }
        """)
        
        # Configure column sizes to EXACTLY match custom header
        header = self.track_table.horizontalHeader()
        
        # Set fixed columns first to match header exactly
        self.track_table.setColumnWidth(2, 90)   # Duration - fixed
        self.track_table.setColumnWidth(3, 140)  # Matched - fixed
        
        # Configure resize modes for proper alignment
        # Two stretching columns (Track, Artist) and one last section stretch (Downloaded)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Track - flexible
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Artist - flexible  
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)    # Duration - fixed 90px
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)    # Matched - fixed 140px
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)  # Downloaded - will be handled by setStretchLastSection
        
        # Let the last section (Downloaded) stretch to fill remaining space
        header.setStretchLastSection(True)
        
        # Better table behavior
        self.track_table.setAlternatingRowColors(True)
        self.track_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.track_table.setShowGrid(True)
        self.track_table.setGridStyle(Qt.PenStyle.SolidLine)
        
        # Set row height for better readability
        self.track_table.verticalHeader().setDefaultSectionSize(35)
        self.track_table.verticalHeader().setVisible(False)
        
        # Populate with initial track data
        self.populate_track_table()
        
        layout.addWidget(header_label)
        layout.addWidget(custom_header)
        layout.addWidget(self.track_table)
        
        return table_frame
    
    def create_custom_header(self):
        """Create a custom header row with visible labels"""
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #1db954;
                border: 1px solid #169441;
                border-radius: 6px;
                padding: 0px;
                margin: 0px;
            }
        """)
        
        layout = QHBoxLayout(header_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        
        # Create header labels with same proportions as table columns
        headers = ["Track", "Artist", "Duration", "Matched", "Downloaded"]
        
        # Track - stretch
        track_label = QLabel("Track")
        track_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #000000;
                font-weight: bold;
                font-size: 13px;
                padding: 12px 8px;
                border-right: 1px solid #169441;
            }
        """)
        track_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Artist - stretch  
        artist_label = QLabel("Artist")
        artist_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #000000;
                font-weight: bold;
                font-size: 13px;
                padding: 12px 8px;
                border-right: 1px solid #169441;
            }
        """)
        artist_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Duration - fixed width
        duration_label = QLabel("Duration")
        duration_label.setFixedWidth(90)
        duration_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #000000;
                font-weight: bold;
                font-size: 13px;
                padding: 12px 8px;
                border-right: 1px solid #169441;
            }
        """)
        duration_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Matched - fixed width
        matched_label = QLabel("Matched")
        matched_label.setFixedWidth(140)
        matched_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #000000;
                font-weight: bold;
                font-size: 13px;
                padding: 12px 8px;
                border-right: 1px solid #169441;
            }
        """)
        matched_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Downloaded - stretch to fill remaining space  
        downloaded_label = QLabel("Downloaded")
        downloaded_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #000000;
                font-weight: bold;
                font-size: 13px;
                padding: 12px 8px;
            }
        """)
        downloaded_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(track_label, stretch=1)
        layout.addWidget(artist_label, stretch=1)
        layout.addWidget(duration_label)
        layout.addWidget(matched_label)
        layout.addWidget(downloaded_label, stretch=1)  # Let it stretch to fill remaining space
        
        return header_frame
        
    def populate_track_table(self):
        """Populate track table with playlist tracks"""
        self.track_table.setRowCount(len(self.playlist.tracks))
        
        for i, track in enumerate(self.playlist.tracks):
            # Track name
            track_item = QTableWidgetItem(track.name)
            track_item.setFlags(track_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.track_table.setItem(i, 0, track_item)
            
            # Artist
            artist_name = track.artists[0] if track.artists else "Unknown Artist"
            artist_item = QTableWidgetItem(artist_name)
            artist_item.setFlags(artist_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.track_table.setItem(i, 1, artist_item)
            
            # Duration
            duration = self.format_duration(track.duration_ms)
            duration_item = QTableWidgetItem(duration)
            duration_item.setFlags(duration_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            duration_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.track_table.setItem(i, 2, duration_item)
            
            # Matched status (initially pending)
            matched_item = QTableWidgetItem("⏳ Pending")
            matched_item.setFlags(matched_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            matched_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.track_table.setItem(i, 3, matched_item)
            
            # Downloaded status (initially pending)
            downloaded_item = QTableWidgetItem("⏳ Pending")
            downloaded_item.setFlags(downloaded_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            downloaded_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.track_table.setItem(i, 4, downloaded_item)
            
    def format_duration(self, duration_ms):
        """Convert milliseconds to MM:SS format"""
        seconds = duration_ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"
        
    def create_buttons(self):
        """Create improved button section"""
        button_frame = QFrame()
        button_frame.setStyleSheet("""
            QFrame {
                background-color: transparent;
                padding: 10px;
            }
        """)
        
        layout = QHBoxLayout(button_frame)
        layout.setSpacing(15)
        layout.setContentsMargins(0, 10, 0, 0)
        
        # Begin Search button
        self.begin_search_btn = QPushButton("Begin Search")
        self.begin_search_btn.setFixedSize(160, 40)
        self.begin_search_btn.clicked.connect(self.on_begin_search_clicked)
        
        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedSize(110, 40)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #f44336;
            }
            QPushButton:pressed {
                background-color: #b71c1c;
            }
        """)
        self.cancel_btn.clicked.connect(self.on_cancel_clicked)
        
        # Close button
        self.close_btn = QPushButton("Close")
        self.close_btn.setFixedSize(110, 40)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #616161;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #757575;
            }
            QPushButton:pressed {
                background-color: #424242;
            }
        """)
        self.close_btn.clicked.connect(self.on_close_clicked)
        
        layout.addStretch()
        layout.addWidget(self.begin_search_btn)
        layout.addWidget(self.cancel_btn)
        layout.addWidget(self.close_btn)
        
        return button_frame
        
    def on_begin_search_clicked(self):
        """Handle Begin Search button click - starts Plex analysis"""
        self.begin_search_btn.setEnabled(False)
        self.begin_search_btn.setText("Searching Plex...")
        
        # Show and reset analysis progress bar
        self.analysis_progress.setVisible(True)
        self.analysis_progress.setMaximum(self.total_tracks)
        self.analysis_progress.setValue(0)
        
        # Start Plex analysis
        self.start_plex_analysis()
        
    def start_plex_analysis(self):
        """Start Plex analysis using existing worker"""
        plex_client = getattr(self.parent_page, 'plex_client', None)
        worker = PlaylistTrackAnalysisWorker(self.playlist.tracks, plex_client)
        
        # Connect signals for live updates
        worker.signals.analysis_started.connect(self.on_analysis_started)
        worker.signals.track_analyzed.connect(self.on_track_analyzed)
        worker.signals.analysis_completed.connect(self.on_analysis_completed)
        worker.signals.analysis_failed.connect(self.on_analysis_failed)
        
        # Track worker for cleanup
        self.active_workers.append(worker)
        
        # Submit to thread pool
        if hasattr(self.parent_page, 'thread_pool'):
            self.parent_page.thread_pool.start(worker)
        else:
            # Create fallback thread pool
            thread_pool = QThreadPool()
            self.fallback_pools.append(thread_pool)
            thread_pool.start(worker)
            
    def on_analysis_started(self, total_tracks):
        """Handle analysis start"""
        print(f"🔍 Analysis started for {total_tracks} tracks")
        
    def on_track_analyzed(self, track_index, result):
        """Handle individual track analysis completion with live UI updates"""
        # Update progress bar
        self.analysis_progress.setValue(track_index)
        
        # Update counters and table
        if result.exists_in_plex:
            # Track found in Plex
            matched_text = f"✅ Found ({result.confidence:.1f})"
            self.matched_tracks_count += 1
            self.matched_count_label.setText(str(self.matched_tracks_count))
        else:
            # Track missing from Plex - will need download
            matched_text = "❌ Missing"
            self.tracks_to_download_count += 1
            self.download_count_label.setText(str(self.tracks_to_download_count))
            
        # Update table row
        matched_item = QTableWidgetItem(matched_text)
        matched_item.setFlags(matched_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        matched_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.track_table.setItem(track_index - 1, 3, matched_item)
        
        print(f"  Track {track_index}: {result.spotify_track.name} - {'Found' if result.exists_in_plex else 'Missing'}")
        
    def on_analysis_completed(self, results):
        """Handle analysis completion"""
        self.analysis_complete = True
        self.analysis_results = results
        self.missing_tracks = [r for r in results if not r.exists_in_plex]
        
        print(f"✅ Analysis complete: {len(self.missing_tracks)} to download, {self.matched_tracks_count} matched")
        
        # Update UI
        self.begin_search_btn.setText("Analysis Complete")
        
        if self.missing_tracks:
            # Automatically start download progress
            self.start_download_progress()
        else:
            QMessageBox.information(self, "Analysis Complete", 
                                  "All tracks already exist in Plex library!\nNo downloads needed.")
            
    def on_analysis_failed(self, error_message):
        """Handle analysis failure"""
        print(f"❌ Analysis failed: {error_message}")
        QMessageBox.critical(self, "Analysis Failed", f"Failed to analyze tracks: {error_message}")
        
        # Reset UI
        self.begin_search_btn.setEnabled(True)
        self.begin_search_btn.setText("Begin Search")
        self.analysis_progress.setVisible(False)
        
    def start_download_progress(self):
        """Start actual download progress tracking"""
        print(f"🚀 Starting download progress for {len(self.missing_tracks)} tracks")
        
        # Show download progress bar
        self.download_progress.setVisible(True)
        self.download_progress.setMaximum(len(self.missing_tracks))
        self.download_progress.setValue(0)
        
        # Start real downloads
        self.start_soulseek_downloads()
        
    def start_soulseek_downloads(self):
        """Start real Soulseek downloads for missing tracks"""
        if not self.missing_tracks:
            return
            
        # Get Soulseek client from parent
        soulseek_client = getattr(self.parent_page, 'soulseek_client', None)
        if not soulseek_client:
            QMessageBox.critical(self, "Soulseek Unavailable", 
                               "Soulseek client not available. Please check your configuration.")
            return
        
        # Create download worker
        self.download_in_progress = True
        self.current_download = 0
        
        # Start downloading first track
        self.download_next_track()
        
    def download_next_track(self):
        """Download the next missing track"""
        if self.current_download >= len(self.missing_tracks):
            # All downloads complete
            self.on_all_downloads_complete()
            return
            
        track_result = self.missing_tracks[self.current_download]
        track = track_result.spotify_track
        track_index = self.find_track_index(track)
        
        print(f"🎵 Downloading track {self.current_download + 1}/{len(self.missing_tracks)}: {track.name}")
        
        # Update table to show downloading status
        if track_index is not None:
            downloading_item = QTableWidgetItem("⏬ Downloading")
            downloading_item.setFlags(downloading_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            downloading_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.track_table.setItem(track_index, 4, downloading_item)
        
        # Create download worker
        soulseek_client = getattr(self.parent_page, 'soulseek_client', None)
        worker = TrackDownloadWorker(track, soulseek_client, self.current_download, track_index)
        worker.signals.download_completed.connect(self.on_track_download_complete)
        worker.signals.download_failed.connect(self.on_track_download_failed)
        
        # Track worker for cleanup
        self.active_workers.append(worker)
        
        # Submit to thread pool
        if hasattr(self.parent_page, 'thread_pool'):
            self.parent_page.thread_pool.start(worker)
        else:
            thread_pool = QThreadPool()
            self.fallback_pools.append(thread_pool)
            thread_pool.start(worker)
            
    def find_track_index(self, spotify_track):
        """Find the table row index for a given Spotify track"""
        for i, playlist_track in enumerate(self.playlist.tracks):
            if (playlist_track.name == spotify_track.name and 
                playlist_track.artists[0] == spotify_track.artists[0]):
                return i
        return None
        
    def on_track_download_complete(self, download_index, track_index, download_id):
        """Handle successful track download"""
        print(f"✅ Download {download_index + 1} completed: {download_id}")
        
        # Update table row
        if track_index is not None:
            downloaded_item = QTableWidgetItem("✅ Downloaded")
            downloaded_item.setFlags(downloaded_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            downloaded_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.track_table.setItem(track_index, 4, downloaded_item)
        
        # Update progress
        self.current_download += 1
        self.download_progress.setValue(self.current_download)
        
        # Continue with next download
        self.download_next_track()
        
    def on_track_download_failed(self, download_index, track_index, error_message):
        """Handle failed track download"""
        print(f"❌ Download {download_index + 1} failed: {error_message}")
        
        # Update table row  
        if track_index is not None:
            failed_item = QTableWidgetItem("❌ Failed")
            failed_item.setFlags(failed_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            failed_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.track_table.setItem(track_index, 4, failed_item)
        
        # Update progress and continue
        self.current_download += 1
        self.download_progress.setValue(self.current_download)
        
        # Continue with next download
        self.download_next_track()
        
    def on_all_downloads_complete(self):
        """Handle completion of all downloads"""
        self.download_in_progress = False
        print("🎉 All downloads completed!")
        
        # Update button text
        self.begin_search_btn.setText("Downloads Complete")
        
        QMessageBox.information(self, "Downloads Complete", 
                              f"Completed downloading {len(self.missing_tracks)} missing tracks!")
    
    def create_progress_bubble(self):
        """Create a progress bubble on the main sync page"""
        if hasattr(self.parent_page, 'create_download_progress_bubble'):
            # Calculate current progress
            total_tracks = len(self.playlist.tracks)
            completed_analysis = self.analysis_progress.value() if self.analysis_complete else 0
            completed_downloads = self.download_progress.value() if self.download_in_progress else 0
            
            progress_info = {
                'playlist_name': self.playlist.name,
                'total_tracks': total_tracks,
                'analysis_complete': self.analysis_complete,
                'analysis_progress': completed_analysis,
                'download_progress': completed_downloads,
                'download_total': len(self.missing_tracks) if hasattr(self, 'missing_tracks') else 0,
                'modal_reference': self  # Keep reference to reopen modal
            }
            
            self.parent_page.create_download_progress_bubble(progress_info)

    def simulate_downloads(self):
        """Simulate download process (placeholder for real implementation)"""
        from PyQt6.QtCore import QTimer
        
        self.current_download = 0
        self.download_timer = QTimer()
        self.download_timer.timeout.connect(self.simulate_next_download)
        self.download_timer.start(1500)  # Simulate 1.5 seconds per download
        
    def simulate_next_download(self):
        """Simulate next download completion"""
        if self.current_download < len(self.missing_tracks):
            # Find the track in the table and update its status
            missing_result = self.missing_tracks[self.current_download]
            
            # Find track index in original playlist
            track_index = None
            for i, track in enumerate(self.playlist.tracks):
                if track.id == missing_result.spotify_track.id:
                    track_index = i
                    break
                    
            if track_index is not None:
                # Update Downloaded column
                downloaded_item = QTableWidgetItem("✅ Complete")
                downloaded_item.setFlags(downloaded_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                downloaded_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.track_table.setItem(track_index, 4, downloaded_item)
            
            # Update progress
            self.current_download += 1
            self.download_progress.setValue(self.current_download)
            
        else:
            # All downloads complete
            self.download_timer.stop()
            self.begin_search_btn.setText("Downloads Complete")
            QMessageBox.information(self, "Downloads Complete", 
                                  f"Successfully downloaded {len(self.missing_tracks)} missing tracks!")
            
    def on_cancel_clicked(self):
        """Handle Cancel button - cancels operations and closes modal"""
        self.cancel_operations()
        self.reject()  # Close modal with cancel result
        
    def on_close_clicked(self):
        """Handle Close button - closes modal without canceling operations"""
        # If operations are in progress, create progress bubble
        if self.download_in_progress or not self.analysis_complete:
            self.create_progress_bubble()
        
        # Close modal without canceling operations
        self.reject()
        
    def cancel_operations(self):
        """Cancel any ongoing operations"""
        # Cancel workers
        for worker in self.active_workers:
            if hasattr(worker, 'cancel'):
                worker.cancel()
                
        # Stop timers
        if hasattr(self, 'download_timer'):
            self.download_timer.stop()
            
        print("🛑 Operations cancelled")
        
    def closeEvent(self, event):
        """Handle modal close event"""
        # Only cancel if user explicitly clicked Cancel
        # For Close button or X button, preserve operations
        event.accept()