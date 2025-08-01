"""
Control panel for fragment manipulation
"""

from typing import Optional
from typing import List
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                            QPushButton, QLabel, QSpinBox, QDoubleSpinBox,
                            QSlider, QCheckBox, QGridLayout, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon

from ..core.fragment import Fragment

class ControlPanel(QWidget):
    """Control panel for fragment transformation and properties"""
    
    transform_requested = pyqtSignal(str, str, object)  # fragment_id, transform_type, value
    reset_transform_requested = pyqtSignal(str)  # fragment_id
    group_transform_requested = pyqtSignal(list, str, object)  # fragment_ids, transform_type, value
    translation_step_changed = pyqtSignal(float)  # step_value
    
    def __init__(self):
        super().__init__()
        self.current_fragment: Optional[Fragment] = None
        self.selected_fragment_ids: List[str] = []
        self.selected_fragment_ids: List[str] = []
        self.translation_step = 10.0  # Default step size
        self.setup_ui()
        self.update_controls()
        
    def setup_ui(self):
        """Setup the control panel UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Fragment info group
        self.info_group = QGroupBox("Fragment Information")
        self.setup_info_group()
        layout.addWidget(self.info_group)
        
        # Transform group
        self.transform_group = QGroupBox("Transformations")
        self.setup_transform_group()
        layout.addWidget(self.transform_group)
        
        # Position group
        self.position_group = QGroupBox("Position")
        self.setup_position_group()
        layout.addWidget(self.position_group)
        
        # Display group
        self.display_group = QGroupBox("Display")
        self.setup_display_group()
        layout.addWidget(self.display_group)
        
        # Group operations (initially hidden)
        self.group_info_widget = QWidget()
        self.setup_group_info()
        layout.addWidget(self.group_info_widget)
        self.group_info_widget.setVisible(False)
        
        # Add stretch to push everything to top
        layout.addStretch()
        
    def setup_info_group(self):
        """Setup fragment information display"""
        layout = QVBoxLayout(self.info_group)
        
        self.name_label = QLabel("No fragment selected")
        self.name_label.setStyleSheet("font-weight: bold; color: #4a90e2;")
        layout.addWidget(self.name_label)
        
        self.size_label = QLabel("Size: -")
        layout.addWidget(self.size_label)
        
        self.file_label = QLabel("File: -")
        self.file_label.setWordWrap(True)
        layout.addWidget(self.file_label)
        
    def setup_transform_group(self):
        """Setup transformation controls"""
        layout = QGridLayout(self.transform_group)
        
        # Rotation controls
        layout.addWidget(QLabel("Rotation:"), 0, 0)
        
        rotation_layout = QHBoxLayout()
        self.rotate_ccw_btn = QPushButton("↺ 90°")
        self.rotate_ccw_btn.clicked.connect(self.on_rotate_ccw_clicked)
        rotation_layout.addWidget(self.rotate_ccw_btn)
        
        self.rotate_cw_btn = QPushButton("↻ 90°")
        self.rotate_cw_btn.clicked.connect(self.on_rotate_cw_clicked)
        rotation_layout.addWidget(self.rotate_cw_btn)
        
        layout.addLayout(rotation_layout, 0, 1)
        
        # Free rotation control
        layout.addWidget(QLabel("Angle:"), 1, 0)
        
        angle_layout = QHBoxLayout()
        self.angle_spinbox = QDoubleSpinBox()
        self.angle_spinbox.setRange(-360.0, 360.0)
        self.angle_spinbox.setDecimals(1)
        self.angle_spinbox.setSuffix("°")
        self.angle_spinbox.valueChanged.connect(self.on_angle_changed)
        angle_layout.addWidget(self.angle_spinbox)
        
        # Quick angle buttons
        angle_45_btn = QPushButton("45°")
        angle_45_btn.clicked.connect(lambda: self.on_angle_button_clicked(45))
        angle_layout.addWidget(angle_45_btn)
        
        angle_neg45_btn = QPushButton("-45°")
        angle_neg45_btn.clicked.connect(lambda: self.on_angle_button_clicked(-45))
        angle_layout.addWidget(angle_neg45_btn)
        
        layout.addLayout(angle_layout, 1, 1)
        
        # Flip controls
        layout.addWidget(QLabel("Flip:"), 2, 0)
        
        flip_layout = QHBoxLayout()
        self.flip_h_btn = QPushButton("↔ Horizontal")
        self.flip_h_btn.clicked.connect(self.on_flip_horizontal_clicked)
        flip_layout.addWidget(self.flip_h_btn)
        
        self.flip_v_btn = QPushButton("↕ Vertical")
        self.flip_v_btn.clicked.connect(self.on_flip_vertical_clicked)
        flip_layout.addWidget(self.flip_v_btn)
        
        layout.addLayout(flip_layout, 2, 1)
        
        # Reset button
        self.reset_btn = QPushButton("Reset All Transforms")
        self.reset_btn.setStyleSheet("QPushButton { background-color: #d32f2f; }")
        self.reset_btn.clicked.connect(self.request_reset)
        layout.addWidget(self.reset_btn, 3, 0, 1, 2)
        
    def setup_position_group(self):
        """Setup position controls"""
        layout = QGridLayout(self.position_group)
        
        # X position
        layout.addWidget(QLabel("X:"), 0, 0)
        self.x_spinbox = QDoubleSpinBox()
        self.x_spinbox.setRange(-999999, 999999)
        self.x_spinbox.setDecimals(1)
        self.x_spinbox.valueChanged.connect(self.on_position_changed)
        layout.addWidget(self.x_spinbox, 0, 1)
        
        # Y position
        layout.addWidget(QLabel("Y:"), 1, 0)
        self.y_spinbox = QDoubleSpinBox()
        self.y_spinbox.setRange(-999999, 999999)
        self.y_spinbox.setDecimals(1)
        self.y_spinbox.valueChanged.connect(self.on_position_changed)
        layout.addWidget(self.y_spinbox, 1, 1)
        
        # Translation buttons
        translation_layout = QGridLayout()
        
        # Translation step control
        step_layout = QHBoxLayout()
        step_layout.addWidget(QLabel("Step:"))
        self.step_spinbox = QDoubleSpinBox()
        self.step_spinbox.setRange(0.1, 1000.0)
        self.step_spinbox.setValue(self.translation_step)
        self.step_spinbox.setDecimals(1)
        self.step_spinbox.setSuffix(" px")
        self.step_spinbox.valueChanged.connect(self.on_translation_step_changed)
        step_layout.addWidget(self.step_spinbox)
        step_layout.addStretch()
        
        layout.addLayout(step_layout, 3, 0, 1, 2)
        
        # Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator, 4, 0, 1, 2)
        
        # Up
        up_btn = QPushButton("↑")
        up_btn.clicked.connect(lambda: self.on_translate_clicked(0, -self.translation_step))
        translation_layout.addWidget(up_btn, 0, 1)
        
        # Left, Center, Right
        left_btn = QPushButton("←")
        left_btn.clicked.connect(lambda: self.on_translate_clicked(-self.translation_step, 0))
        translation_layout.addWidget(left_btn, 1, 0)
        
        center_btn = QPushButton("⌂")
        center_btn.setToolTip("Center fragment")
        center_btn.clicked.connect(self.on_center_clicked)
        translation_layout.addWidget(center_btn, 1, 1)
        
        right_btn = QPushButton("→")
        right_btn.clicked.connect(lambda: self.on_translate_clicked(self.translation_step, 0))
        translation_layout.addWidget(right_btn, 1, 2)
        
        # Down
        down_btn = QPushButton("↓")
        down_btn.clicked.connect(lambda: self.on_translate_clicked(0, self.translation_step))
        translation_layout.addWidget(down_btn, 2, 1)
        
        layout.addLayout(translation_layout, 5, 0, 1, 2)
        
    def setup_group_info(self):
        """Setup group information display"""
        layout = QVBoxLayout(self.group_info_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Group info
        self.group_info_label = QLabel("0 fragments selected")
        self.group_info_label.setStyleSheet("font-weight: bold; color: #ff8c00; padding: 5px; background-color: #3d3d3d; border-radius: 3px;")
        layout.addWidget(self.group_info_label)
        
        # Clear selection button
        self.clear_selection_btn = QPushButton("Clear Group Selection")
        self.clear_selection_btn.clicked.connect(self.clear_group_selection)
        layout.addWidget(self.clear_selection_btn)
        
    def setup_display_group(self):
        """Setup display controls"""
        layout = QVBoxLayout(self.display_group)
        
        # Visibility checkbox
        self.visible_checkbox = QCheckBox("Visible")
        self.visible_checkbox.stateChanged.connect(self.on_visibility_changed)
        layout.addWidget(self.visible_checkbox)
        
        # Opacity slider
        opacity_layout = QHBoxLayout()
        opacity_layout.addWidget(QLabel("Opacity:"))
        
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.valueChanged.connect(self.on_opacity_changed)
        opacity_layout.addWidget(self.opacity_slider)
        
        self.opacity_label = QLabel("100%")
        self.opacity_label.setMinimumWidth(40)
        opacity_layout.addWidget(self.opacity_label)
        
        layout.addLayout(opacity_layout)
        
    def set_selected_fragment(self, fragment: Optional[Fragment]):
        """Set the currently selected fragment"""
        self.current_fragment = fragment
        self.update_controls()
        
    def set_selected_fragments(self, fragment_ids: List[str]):
        """Set the group selected fragments"""
        self.selected_fragment_ids = fragment_ids
        self.update_group_controls()
        
    def clear_group_selection(self):
        """Clear group selection"""
        self.selected_fragment_ids.clear()
        self.update_group_controls()
        
    def update_controls(self):
        """Update control states based on current fragment"""
        has_fragment = self.current_fragment is not None
        has_group = len(self.selected_fragment_ids) > 0
        
        # Enable/disable controls - enable if we have either individual fragment or group
        self.transform_group.setEnabled(has_fragment or has_group)
        self.position_group.setEnabled(has_fragment or has_group)
        self.display_group.setEnabled(has_fragment and not has_group)  # Only for individual fragments
        
        # Update tooltips based on mode
        if has_group:
            self.rotate_ccw_btn.setToolTip("Rotate group counter-clockwise")
            self.rotate_cw_btn.setToolTip("Rotate group clockwise")
            self.flip_h_btn.setToolTip("Flip group horizontally")
            self.flip_v_btn.setToolTip("Flip group vertically")
        else:
            self.rotate_ccw_btn.setToolTip("Rotate counter-clockwise")
            self.rotate_cw_btn.setToolTip("Rotate clockwise")
            self.flip_h_btn.setToolTip("Flip horizontally")
            self.flip_v_btn.setToolTip("Flip vertically")
        
        if not has_fragment and not has_group:
            self.name_label.setText("No fragment selected")
            self.size_label.setText("Size: -")
            self.file_label.setText("File: -")
            return
            
        if has_group:
            # Group mode - show group info
            count = len(self.selected_fragment_ids)
            self.name_label.setText(f"Group Selection ({count} fragments)")
            self.size_label.setText("Size: Multiple")
            self.file_label.setText("File: Multiple")
            
            # Disable individual controls that don't make sense for groups
            self.x_spinbox.setEnabled(False)
            self.y_spinbox.setEnabled(False)
            self.angle_spinbox.setEnabled(False)
        else:
            # Individual fragment mode
            fragment = self.current_fragment
            
            # Update info
            self.name_label.setText(fragment.name or f"Fragment {fragment.id[:8]}")
            self.size_label.setText(f"Size: {fragment.original_size[0]} × {fragment.original_size[1]}")
            self.file_label.setText(f"File: {fragment.file_path}")
            
            # Enable individual controls
            self.x_spinbox.setEnabled(True)
            self.y_spinbox.setEnabled(True)
            self.angle_spinbox.setEnabled(True)
            
            # Update position controls (block signals to prevent recursion)
            self.x_spinbox.blockSignals(True)
            self.y_spinbox.blockSignals(True)
            self.x_spinbox.setValue(fragment.x)
            self.y_spinbox.setValue(fragment.y)
            self.x_spinbox.blockSignals(False)
            self.y_spinbox.blockSignals(False)
            
            # Update angle control
            self.angle_spinbox.blockSignals(True)
            self.angle_spinbox.setValue(fragment.rotation)
            self.angle_spinbox.blockSignals(False)
            
            # Update display controls
            self.visible_checkbox.blockSignals(True)
            self.visible_checkbox.setChecked(fragment.visible)
            self.visible_checkbox.blockSignals(False)
            
            self.opacity_slider.blockSignals(True)
            self.opacity_slider.setValue(int(fragment.opacity * 100))
            self.opacity_label.setText(f"{int(fragment.opacity * 100)}%")
            self.opacity_slider.blockSignals(False)
            
            # Update transform button states
            self.update_transform_button_states()
        
    def update_group_controls(self):
        """Update group operation controls"""
        has_group = len(self.selected_fragment_ids) > 0
        self.group_info_widget.setVisible(has_group)
        
        if has_group:
            count = len(self.selected_fragment_ids)
            self.group_info_label.setText(f"{count} fragment{'s' if count != 1 else ''} selected")
            
        # Update the main controls to reflect the current mode
        self.update_controls()
        
    def update_transform_button_states(self):
        """Update the visual state of transform buttons"""
        if not self.current_fragment:
            return
            
        fragment = self.current_fragment
        
        # Update flip button styles based on current state
        if fragment.flip_horizontal:
            self.flip_h_btn.setStyleSheet("QPushButton { background-color: #4a90e2; }")
        else:
            self.flip_h_btn.setStyleSheet("")
            
        if fragment.flip_vertical:
            self.flip_v_btn.setStyleSheet("QPushButton { background-color: #4a90e2; }")
        else:
            self.flip_v_btn.setStyleSheet("")
            
    # Event handlers that work for both individual and group modes
    def on_rotate_ccw_clicked(self):
        """Handle counter-clockwise rotation"""
        if self.selected_fragment_ids:
            self.group_transform_requested.emit(self.selected_fragment_ids, 'rotate_ccw', None)
        elif self.current_fragment:
            self.transform_requested.emit(self.current_fragment.id, 'rotate_ccw', None)
            
    def on_rotate_cw_clicked(self):
        """Handle clockwise rotation"""
        if self.selected_fragment_ids:
            self.group_transform_requested.emit(self.selected_fragment_ids, 'rotate_cw', None)
        elif self.current_fragment:
            self.transform_requested.emit(self.current_fragment.id, 'rotate_cw', None)
            
    def on_angle_button_clicked(self, angle: float):
        """Handle angle button clicks"""
        if self.selected_fragment_ids:
            self.group_transform_requested.emit(self.selected_fragment_ids, 'rotate_angle', angle)
        elif self.current_fragment:
            self.transform_requested.emit(self.current_fragment.id, 'rotate_angle', angle)
            
    def on_flip_horizontal_clicked(self):
        """Handle horizontal flip"""
        if self.selected_fragment_ids:
            self.group_transform_requested.emit(self.selected_fragment_ids, 'flip_horizontal', None)
        elif self.current_fragment:
            self.transform_requested.emit(self.current_fragment.id, 'flip_horizontal', None)
            
    def on_flip_vertical_clicked(self):
        """Handle vertical flip"""
        if self.selected_fragment_ids:
            self.group_transform_requested.emit(self.selected_fragment_ids, 'flip_vertical', None)
        elif self.current_fragment:
            self.transform_requested.emit(self.current_fragment.id, 'flip_vertical', None)
            
    def on_translate_clicked(self, dx: float, dy: float):
        """Handle translation button clicks"""
        if self.selected_fragment_ids:
            self.group_transform_requested.emit(self.selected_fragment_ids, 'translate', (dx, dy))
        elif self.current_fragment:
            self.transform_requested.emit(self.current_fragment.id, 'translate', (dx, dy))
        
        # Force immediate update
        self.update_controls()
            
    def on_center_clicked(self):
        """Handle center button click"""
        if self.current_fragment:  # Only works for individual fragments
            self.transform_requested.emit(self.current_fragment.id, 'translate', (0, 0))
        
        # Force immediate update
        self.update_controls()
            
    def request_transform(self, transform_type: str, value=None):
        """Request a transformation for the current fragment (legacy method)"""
        if self.selected_fragment_ids:
            self.group_transform_requested.emit(self.selected_fragment_ids, transform_type, value)
        elif self.current_fragment:
            self.transform_requested.emit(self.current_fragment.id, transform_type, value)
            
    def request_group_transform(self, transform_type: str, value=None):
        """Request a transformation for the selected group (legacy method)"""
        if self.selected_fragment_ids:
            self.group_transform_requested.emit(self.selected_fragment_ids, transform_type, value)
            
    def request_reset(self):
        """Request reset of current fragment transforms"""
        if self.current_fragment:
            self.reset_transform_requested.emit(self.current_fragment.id)
            
    def on_position_changed(self):
        """Handle position spinbox changes"""
        if self.current_fragment:
            new_x = self.x_spinbox.value()
            new_y = self.y_spinbox.value()
            self.request_transform('translate', (new_x - self.current_fragment.x, 
                                               new_y - self.current_fragment.y))
            
    def on_visibility_changed(self, state):
        """Handle visibility checkbox changes"""
        if self.current_fragment:
            visible = state == Qt.CheckState.Checked.value
            self.transform_requested.emit(self.current_fragment.id, 'set_visibility', visible)
        
        # Force immediate update
        self.update_controls()
            
    def on_opacity_changed(self, value):
        """Handle opacity slider changes"""
        if self.current_fragment:
            opacity = value / 100.0
            self.current_fragment.opacity = opacity
            self.opacity_label.setText(f"{value}%")
        
        # Force immediate update
        self.update_controls()
            
    def on_angle_changed(self):
        """Handle angle spinbox changes"""
        if self.current_fragment and not self.selected_fragment_ids:  # Only for individual fragments
            new_angle = self.angle_spinbox.value()
            self.request_transform('set_rotation', new_angle)
        
        # Force immediate update
        self.update_controls()
            
    def on_translation_step_changed(self):
        """Handle translation step changes"""
        self.translation_step = self.step_spinbox.value()
        self.translation_step_changed.emit(self.translation_step)