"""
Main application window for Tissue Fragment Arrangement and Rigid Stitching UI
"""

import os
import json
import numpy as np
from typing import Dict, List, Optional
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
                            QSplitter, QMenuBar, QStatusBar, QFileDialog, 
                            QMessageBox, QProgressBar, QLabel)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence

from .core.fragment_manager import FragmentManager
from .core.image_loader import ImageLoader
from .ui.canvas_widget import CanvasWidget
from .ui.control_panel import ControlPanel
from .ui.fragment_list import FragmentListWidget
from .ui.toolbar import ToolbarWidget
from .utils.export_manager import ExportManager
from .algorithms.rigid_stitching import RigidStitchingAlgorithm

class MainWindow(QMainWindow):
    """Main application window"""
    
    fragment_selected = pyqtSignal(str)  # fragment_id
    fragments_updated = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.fragment_manager = FragmentManager()
        self.image_loader = ImageLoader()
        self.export_manager = ExportManager()
        self.stitching_algorithm = RigidStitchingAlgorithm()
        
        self.setup_ui()
        self.setup_connections()
        self.setup_menu_bar()
        self.setup_status_bar()
        
        # Set window properties
        self.setWindowTitle("Tissue Fragment Arrangement and Rigid Stitching")
        self.setMinimumSize(1200, 800)
        self.resize(1600, 1000)
        
    def setup_ui(self):
        """Setup the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left panel (fragment list and controls)
        left_panel = QWidget()
        left_panel.setMaximumWidth(350)
        left_panel.setMinimumWidth(300)
        left_layout = QVBoxLayout(left_panel)
        
        # Toolbar
        self.toolbar = ToolbarWidget()
        left_layout.addWidget(self.toolbar)
        
        # Fragment list
        self.fragment_list = FragmentListWidget()
        left_layout.addWidget(self.fragment_list)
        
        # Control panel
        self.control_panel = ControlPanel()
        left_layout.addWidget(self.control_panel)
        
        # Canvas widget (main display area)
        self.canvas_widget = CanvasWidget()
        
        # Add to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(self.canvas_widget)
        
        # Set splitter proportions
        splitter.setSizes([350, 1250])
        
    def setup_connections(self):
        """Setup signal-slot connections"""
        # Toolbar connections
        self.toolbar.load_images_requested.connect(self.load_images)
        self.toolbar.export_requested.connect(self.export_results)
        self.toolbar.stitch_requested.connect(self.perform_stitching)
        self.toolbar.reset_requested.connect(self.reset_fragments)
        self.toolbar.delete_requested.connect(self.delete_selected_fragment)
        
        # Fragment list connections
        self.fragment_list.fragment_selected.connect(self.select_fragment)
        self.fragment_list.fragment_visibility_changed.connect(self.toggle_fragment_visibility)
        self.fragment_list.fragment_delete_requested.connect(self.delete_fragment)
        
        # Control panel connections
        self.control_panel.transform_requested.connect(self.apply_transform)
        self.control_panel.reset_transform_requested.connect(self.reset_fragment_transform)
        
        # Canvas connections
        self.canvas_widget.fragment_selected.connect(self.select_fragment)
        self.canvas_widget.fragment_moved.connect(self.update_fragment_position)
        self.canvas_widget.delete_requested.connect(self.delete_fragment)
        self.canvas_widget.group_selected.connect(self.on_group_selected)
        self.canvas_widget.group_transform_requested.connect(self.apply_group_transform)
        self.control_panel.group_transform_requested.connect(self.apply_group_transform)
        
        # Fragment manager connections
        self.fragment_manager.fragments_changed.connect(self.update_ui)
        self.fragment_manager.fragments_changed.connect(self.on_fragments_changed)
        
    def on_fragments_changed(self):
        """Handle fragment changes and update canvas efficiently"""
        # Update canvas with new fragment data
        self.canvas_widget.update_fragments(self.fragment_manager.get_all_fragments())
        
        # Update control panel for selected fragment
        selected_fragment = self.fragment_manager.get_selected_fragment()
        self.control_panel.set_selected_fragment(selected_fragment)
        
        # Update toolbar with fragment count
        fragment_count = len(self.fragment_manager.get_all_fragments())
        self.toolbar.set_fragment_count(fragment_count)
        
    def on_group_selected(self, fragment_ids: List[str]):
        """Handle group selection from canvas"""
        self.control_panel.set_selected_fragments(fragment_ids)
        
    def on_group_selected(self, fragment_ids: List[str]):
        """Handle group selection from canvas"""
        self.control_panel.set_selected_fragments(fragment_ids)
        
    def setup_menu_bar(self):
        """Setup the menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('&File')
        
        load_action = QAction('&Load Images...', self)
        load_action.setShortcut(QKeySequence.StandardKey.Open)
        load_action.triggered.connect(self.load_images)
        file_menu.addAction(load_action)
        
        file_menu.addSeparator()
        
        export_image_action = QAction('Export &Image...', self)
        export_image_action.setShortcut(QKeySequence('Ctrl+E'))
        export_image_action.triggered.connect(self.export_image)
        file_menu.addAction(export_image_action)
        
        export_metadata_action = QAction('Export &Metadata...', self)
        export_metadata_action.setShortcut(QKeySequence('Ctrl+M'))
        export_metadata_action.triggered.connect(self.export_metadata)
        file_menu.addAction(export_metadata_action)
        
        file_menu.addSeparator()
        
        quit_action = QAction('&Quit', self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu('&Edit')
        
        reset_action = QAction('&Reset All Transforms', self)
        reset_action.setShortcut(QKeySequence('Ctrl+R'))
        reset_action.triggered.connect(self.reset_fragments)
        edit_menu.addAction(reset_action)
        
        edit_menu.addSeparator()
        
        delete_action = QAction('&Delete Selected Fragment', self)
        delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        delete_action.triggered.connect(self.delete_selected_fragment)
        edit_menu.addAction(delete_action)
        
        # View menu
        view_menu = menubar.addMenu('&View')
        
        zoom_fit_action = QAction('Zoom to &Fit', self)
        zoom_fit_action.setShortcut(QKeySequence('Ctrl+0'))
        zoom_fit_action.triggered.connect(self.canvas_widget.zoom_to_fit)
        view_menu.addAction(zoom_fit_action)
        
        zoom_100_action = QAction('Zoom &100%', self)
        zoom_100_action.setShortcut(QKeySequence('Ctrl+1'))
        zoom_100_action.triggered.connect(self.canvas_widget.zoom_to_100)
        view_menu.addAction(zoom_100_action)
        
        # Tools menu
        tools_menu = menubar.addMenu('&Tools')
        
        # Rectangle selection action
        self.rect_select_action = QAction('&Rectangle Selection', self)
        self.rect_select_action.setShortcut(QKeySequence('R'))
        self.rect_select_action.setCheckable(True)
        self.rect_select_action.triggered.connect(self.toggle_selection_mode)
        tools_menu.addAction(self.rect_select_action)
        
        tools_menu.addSeparator()
        
        stitch_action = QAction('&Rigid Stitching', self)
        stitch_action.setShortcut(QKeySequence('Ctrl+S'))
        stitch_action.triggered.connect(self.perform_stitching)
        tools_menu.addAction(stitch_action)
        
    def toggle_selection_mode(self):
        """Toggle rectangle selection mode"""
        selection_mode = self.rect_select_action.isChecked()
        self.canvas_widget.set_selection_mode(selection_mode)
        
    def setup_status_bar(self):
        """Setup the status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Status labels
        self.fragment_count_label = QLabel("Fragments: 0")
        self.zoom_label = QLabel("Zoom: 100%")
        self.position_label = QLabel("Position: (0, 0)")
        
        self.status_bar.addWidget(self.fragment_count_label)
        self.status_bar.addPermanentWidget(self.position_label)
        self.status_bar.addPermanentWidget(self.zoom_label)
        
        # Progress bar for operations
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
    def load_images(self):
        """Load tissue fragment images"""
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        file_dialog.setNameFilter("Image files (*.tiff *.tif *.svs *.png *.jpg)")
        
        if file_dialog.exec():
            file_paths = file_dialog.selectedFiles()
            self.load_images_from_paths(file_paths)
            
    def load_images_from_paths(self, file_paths: List[str]):
        """Load images from file paths"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(file_paths))
        
        try:
            for i, file_path in enumerate(file_paths):
                self.progress_bar.setValue(i)
                self.status_bar.showMessage(f"Loading {os.path.basename(file_path)}...")
                
                # Load image using image loader
                image_data = self.image_loader.load_image(file_path)
                if image_data is not None:
                    # Create fragment from image
                    fragment_id = self.fragment_manager.add_fragment_from_image(
                        image_data, os.path.basename(file_path)
                    )
                    
            self.progress_bar.setValue(len(file_paths))
            self.status_bar.showMessage(f"Loaded {len(file_paths)} fragments", 3000)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load images: {str(e)}")
        finally:
            self.progress_bar.setVisible(False)
            
    def select_fragment(self, fragment_id: str):
        """Select a fragment"""
        self.fragment_manager.set_selected_fragment(fragment_id)
        self.fragment_list.set_selected_fragment(fragment_id)
        self.control_panel.set_selected_fragment(
            self.fragment_manager.get_fragment(fragment_id)
        )
        self.canvas_widget.set_selected_fragment(fragment_id)
        
    def toggle_fragment_visibility(self, fragment_id: str, visible: bool):
        """Toggle fragment visibility"""
        self.fragment_manager.set_fragment_visibility(fragment_id, visible)
        
    def delete_fragment(self, fragment_id: str):
        """Delete a fragment with confirmation"""
        fragment = self.fragment_manager.get_fragment(fragment_id)
        if not fragment:
            return
            
        reply = QMessageBox.question(
            self, "Delete Fragment", 
            f"Are you sure you want to delete fragment '{fragment.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.fragment_manager.remove_fragment(fragment_id)
            self.status_bar.showMessage(f"Fragment '{fragment.name}' deleted", 2000)
            
    def delete_selected_fragment(self):
        """Delete the currently selected fragment"""
        selected_id = self.fragment_manager.get_selected_fragment_id()
        if selected_id:
            self.delete_fragment(selected_id)
        
    def apply_transform(self, fragment_id: str, transform_type: str, value=None):
        """Apply transformation to fragment"""
        fragment = self.fragment_manager.get_fragment(fragment_id)
        if not fragment:
            return
            
        if transform_type == 'rotate_cw':
            self.fragment_manager.rotate_fragment(fragment_id, 90)
        elif transform_type == 'rotate_ccw':
            self.fragment_manager.rotate_fragment(fragment_id, -90)
        elif transform_type == 'rotate_angle':
            self.fragment_manager.rotate_fragment(fragment_id, value)
        elif transform_type == 'set_rotation':
            self.fragment_manager.set_fragment_rotation(fragment_id, value)
        elif transform_type == 'flip_horizontal':
            self.fragment_manager.flip_fragment(fragment_id, horizontal=True)
        elif transform_type == 'flip_vertical':
            self.fragment_manager.flip_fragment(fragment_id, horizontal=False)
        elif transform_type == 'translate':
            dx, dy = value
            self.fragment_manager.translate_fragment(fragment_id, dx, dy)
        elif transform_type == 'set_visibility':
            self.fragment_manager.set_fragment_visibility(fragment_id, value)
            
        # Force immediate canvas update
        self.canvas_widget.update()
            
    def reset_fragment_transform(self, fragment_id: str):
        """Reset fragment transformation"""
        self.fragment_manager.reset_fragment_transform(fragment_id)
        
    def update_fragment_position(self, fragment_id: str, x: float, y: float):
        """Update fragment position from canvas interaction"""
        # Ensure position is properly rounded to avoid floating point precision issues
        x = round(float(x), 2)
        y = round(float(y), 2)
        
        # Debug output
        fragment = self.fragment_manager.get_fragment(fragment_id)
        if fragment:
            print(f"Updating fragment {fragment.name} position: ({fragment.x}, {fragment.y}) -> ({x}, {y})")
        
        self.fragment_manager.set_fragment_position(fragment_id, x, y)
        
    def apply_group_transform(self, fragment_ids: List[str], transform_type: str, value=None):
        """Apply transformation to a group of fragments"""
        # Delegate to canvas widget for immediate rendering
        self.canvas_widget.apply_group_transform(fragment_ids, transform_type, value)
        
        # Update fragment manager state
        for fragment_id in fragment_ids:
            fragment = self.canvas_widget.get_fragment_by_id(fragment_id)
            if fragment:
                # Sync the fragment manager with canvas changes
                manager_fragment = self.fragment_manager.get_fragment(fragment_id)
                if manager_fragment:
                    manager_fragment.x = fragment.x
                    manager_fragment.y = fragment.y
                    manager_fragment.rotation = fragment.rotation
                    manager_fragment.flip_horizontal = fragment.flip_horizontal
                    manager_fragment.flip_vertical = fragment.flip_vertical
                    manager_fragment.invalidate_cache()
        
        # Emit fragments changed to update UI
        self.fragment_manager.fragments_changed.emit()
        
    def perform_stitching(self):
        """Perform rigid stitching refinement"""
        fragments = self.fragment_manager.get_all_fragments()
        if len(fragments) < 2:
            QMessageBox.information(self, "Info", "Need at least 2 fragments for stitching")
            return
            
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.status_bar.showMessage("Performing rigid stitching...")
        
        try:
            # Use current transforms as initial guesses
            initial_transforms = {}
            for fragment in fragments:
                initial_transforms[fragment.id] = {
                    'rotation': fragment.rotation,
                    'translation': (fragment.x, fragment.y),
                    'flip_horizontal': fragment.flip_horizontal
                }
                
            # Perform stitching
            refined_transforms = self.stitching_algorithm.stitch_fragments(
                fragments, initial_transforms
            )
            
            # Apply refined transforms
            for fragment_id, transform in refined_transforms.items():
                fragment = self.fragment_manager.get_fragment(fragment_id)
                if fragment:
                    self.fragment_manager.set_fragment_transform(
                        fragment_id,
                        rotation=transform['rotation'],
                        translation=transform['translation'],
                        flip_horizontal=transform['flip_horizontal']
                    )
                    
            self.status_bar.showMessage("Rigid stitching completed", 3000)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Stitching failed: {str(e)}")
        finally:
            self.progress_bar.setVisible(False)
            
    def reset_fragments(self):
        """Reset all fragment transformations"""
        reply = QMessageBox.question(
            self, "Confirm Reset", 
            "Reset all fragment transformations to default?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.fragment_manager.reset_all_transforms()
            
    def export_results(self):
        """Export both image and metadata"""
        self.export_image()
        self.export_metadata()
        
    def export_image(self):
        """Export the composite image"""
        file_dialog = QFileDialog()
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setNameFilter("Image files (*.tiff *.tif *.png)")
        file_dialog.setDefaultSuffix("tiff")
        
        if file_dialog.exec():
            file_path = file_dialog.selectedFiles()[0]
            try:
                self.export_manager.export_composite_image(
                    self.fragment_manager.get_all_fragments(),
                    file_path
                )
                self.status_bar.showMessage(f"Image exported to {file_path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Export failed: {str(e)}")
                
    def export_metadata(self):
        """Export fragment metadata"""
        file_dialog = QFileDialog()
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setNameFilter("JSON files (*.json)")
        file_dialog.setDefaultSuffix("json")
        
        if file_dialog.exec():
            file_path = file_dialog.selectedFiles()[0]
            try:
                metadata = self.fragment_manager.export_metadata()
                with open(file_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                self.status_bar.showMessage(f"Metadata exported to {file_path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Export failed: {str(e)}")
                
    def update_ui(self):
        """Update UI elements when fragments change"""
        fragments = self.fragment_manager.get_all_fragments()
        
        # Update fragment list
        self.fragment_list.update_fragments(fragments)
        
        # Update canvas
        self.canvas_widget.update_fragments(fragments)
        
        # Update status bar
        self.fragment_count_label.setText(f"Fragments: {len(fragments)}")
        
        # Update control panel if fragment is selected
        selected_id = self.fragment_manager.get_selected_fragment_id()
        if selected_id:
            selected_fragment = self.fragment_manager.get_fragment(selected_id)
            self.control_panel.set_selected_fragment(selected_fragment)