"""
High-performance canvas widget for tissue fragment visualization
"""

import numpy as np
from typing import List, Optional, Tuple, Dict
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint, QRect, QThread, QObject
from PyQt6.QtGui import (QPainter, QPixmap, QImage, QPen, QBrush, QColor, QPolygon,
                        QMouseEvent, QWheelEvent, QPaintEvent, QResizeEvent, QTransform, QKeyEvent)
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import QPointF
import cv2

from ..core.fragment import Fragment

class FragmentRenderer(QObject):
    """Background fragment renderer for better performance"""
    
    rendering_finished = pyqtSignal(str, QPixmap)  # fragment_id, pixmap
    
    def __init__(self):
        super().__init__()
        self.render_queue = []
        
    def render_fragment(self, fragment: Fragment, zoom: float):
        """Render a single fragment at the given zoom level"""
        if fragment.image_data is None:
            return
            
        transformed_image = fragment.get_transformed_image()
        if transformed_image is None:
            return
            
        # Apply level-of-detail based on zoom
        if zoom < 0.25:
            # Very low zoom - use 1/4 resolution
            scale_factor = 0.25
        elif zoom < 0.5:
            # Low zoom - use 1/2 resolution
            scale_factor = 0.5
        elif zoom > 4.0:
            # High zoom - use full resolution
            scale_factor = 1.0
        else:
            # Normal zoom - use full resolution
            scale_factor = 1.0
            
        # Resize if needed for LOD
        if scale_factor < 1.0:
            new_height = int(transformed_image.shape[0] * scale_factor)
            new_width = int(transformed_image.shape[1] * scale_factor)
            if new_height > 0 and new_width > 0:
                transformed_image = cv2.resize(transformed_image, (new_width, new_height), 
                                             interpolation=cv2.INTER_AREA)
        
        # Convert to QPixmap
        height, width = transformed_image.shape[:2]
        if len(transformed_image.shape) == 3 and transformed_image.shape[2] == 4:
            # RGBA
            bytes_per_line = 4 * width
            q_image = QImage(transformed_image.data, width, height, bytes_per_line, QImage.Format.Format_RGBA8888)
        else:
            # Fallback to RGB
            if len(transformed_image.shape) == 3:
                bytes_per_line = 3 * width
                q_image = QImage(transformed_image.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
            else:
                return
                
        pixmap = QPixmap.fromImage(q_image)
        
        # Scale back up if we used LOD
        if scale_factor < 1.0:
            original_size = fragment.get_transformed_image().shape[:2]
            pixmap = pixmap.scaled(original_size[1], original_size[0], 
                                 Qt.AspectRatioMode.IgnoreAspectRatio, 
                                 Qt.TransformationMode.FastTransformation)
        
        self.rendering_finished.emit(fragment.id, pixmap)

class CanvasWidget(QWidget):
    """Optimized canvas for tissue fragment display"""
    
    fragment_selected = pyqtSignal(str)  # fragment_id
    fragment_moved = pyqtSignal(str, float, float)  # fragment_id, x, y
    viewport_changed = pyqtSignal(float, float, float)  # zoom, pan_x, pan_y
    delete_requested = pyqtSignal(str)  # fragment_id
    group_selected = pyqtSignal(list)  # list of fragment_ids
    group_transform_requested = pyqtSignal(list, str, object)  # fragment_ids, transform_type, value
    
    def __init__(self):
        super().__init__()
        self.fragments: List[Fragment] = []
        self.selected_fragment_id: Optional[str] = None
        self.selected_fragment_ids: List[str] = []  # For group selection
        
        # Viewport state
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.min_zoom = 0.01
        self.max_zoom = 50.0
        
        # Interaction state
        self.is_panning = False
        self.is_dragging_fragment = False
        self.last_mouse_pos = QPoint()
        self.dragged_fragment_id: Optional[str] = None
        self.drag_offset = QPoint()
        
        # Rectangle selection state
        self.selection_mode = False
        self.selection_start = QPoint()
        self.selection_current = QPoint()
        self.selection_rect = QRect()
        self.is_selecting = False
        
        # Fragment rendering cache
        self.fragment_pixmaps: Dict[str, QPixmap] = {}
        self.fragment_zoom_cache: Dict[str, float] = {}
        self.dirty_fragments: set = set()
        
        # Performance settings
        self.use_lod = True
        self.lod_threshold = 0.5
        self.max_texture_size = 4096
        
        # Rendering optimization
        self.background_color = QColor(42, 42, 42)
        self.selection_color = QColor(74, 144, 226)
        self.group_selection_color = QColor(255, 165, 0)  # Orange for group selection
        self.selection_rect_color = QColor(74, 144, 226, 100)  # Semi-transparent blue
        self.selection_pen_width = 2.0
        
        # Update timers
        self.fast_update_timer = QTimer()
        self.fast_update_timer.setSingleShot(True)
        self.fast_update_timer.timeout.connect(self.update)
        
        self.render_timer = QTimer()
        self.render_timer.setSingleShot(True)
        self.render_timer.timeout.connect(self.render_dirty_fragments)
        
        # Background renderer
        self.renderer = FragmentRenderer()
        self.renderer.rendering_finished.connect(self.on_fragment_rendered)
        
        # Setup
        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # Enable double buffering
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        
    def update_fragments(self, fragments: List[Fragment]):
        """Update the fragment list and mark for re-rendering"""
        # Find which fragments are new or changed
        old_fragment_ids = set(f.id for f in self.fragments)
        new_fragment_ids = set(f.id for f in fragments)
        
        # Remove pixmaps for deleted fragments
        for fragment_id in old_fragment_ids - new_fragment_ids:
            self.fragment_pixmaps.pop(fragment_id, None)
            self.fragment_zoom_cache.pop(fragment_id, None)
            
        # Always update fragments and check for changes
        for fragment in fragments:
            old_fragment = next((f for f in self.fragments if f.id == fragment.id), None)
            
            # Always mark as dirty if fragment is new or cache is invalid
            needs_update = (fragment.id not in old_fragment_ids or not fragment.cache_valid)
            
            # Check for any changes that require re-rendering
            if old_fragment:
                # Check for transform changes (these affect the image itself)
                transform_changed = (
                    abs(old_fragment.rotation - fragment.rotation) > 0.01 or
                    old_fragment.flip_horizontal != fragment.flip_horizontal or
                    old_fragment.flip_vertical != fragment.flip_vertical
                )
                
                # Check for position changes (these don't affect the image, just placement)
                position_changed = (
                    abs(old_fragment.x - fragment.x) > 0.01 or
                    abs(old_fragment.y - fragment.y) > 0.01
                )
                
                # Check for visibility changes
                visibility_changed = old_fragment.visible != fragment.visible
                
                if transform_changed or visibility_changed:
                    needs_update = True
                elif position_changed:
                    # Position changes don't require re-rendering, just re-display
                    pass
            
            if needs_update:
                self.dirty_fragments.add(fragment.id)
                self.fragment_pixmaps.pop(fragment.id, None)
                self.fragment_zoom_cache.pop(fragment.id, None)
                
            # Remove pixmap for invisible fragments
            if not fragment.visible:
                self.fragment_pixmaps.pop(fragment.id, None)
                self.fragment_zoom_cache.pop(fragment.id, None)
                
        self.fragments = fragments
        self.schedule_render()
        
    def set_selection_mode(self, enabled: bool):
        """Enable or disable rectangle selection mode"""
        self.selection_mode = enabled
        if not enabled:
            self.clear_group_selection()
        self.update()
        
    def set_selected_fragment(self, fragment_id: Optional[str], clear_group: bool = True):
        """Set the selected fragment"""
        if clear_group:
            self.selected_fragment_ids.clear()
            
        if self.selected_fragment_id != fragment_id:
            self.selected_fragment_id = fragment_id
            self.update()  # Just update display, no re-rendering needed
            
    def add_to_group_selection(self, fragment_ids: List[str]):
        """Add fragments to group selection"""
        for frag_id in fragment_ids:
            if frag_id not in self.selected_fragment_ids:
                self.selected_fragment_ids.append(frag_id)
        self.group_selected.emit(self.selected_fragment_ids.copy())
        self.update()
        
    def clear_group_selection(self):
        """Clear group selection"""
        self.selected_fragment_ids.clear()
        self.update()
        
    def get_fragments_in_rect(self, rect: QRect) -> List[str]:
        """Get fragment IDs that intersect with the given rectangle"""
        selected_ids = []
        world_rect = QRect(
            int(rect.x() / self.zoom - self.pan_x),
            int(rect.y() / self.zoom - self.pan_y),
            int(rect.width() / self.zoom),
            int(rect.height() / self.zoom)
        )
        
        for fragment in self.fragments:
            if not fragment.visible:
                continue
                
            bbox = fragment.get_bounding_box()
            frag_rect = QRect(int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
            
            if world_rect.intersects(frag_rect):
                selected_ids.append(fragment.id)
                
        return selected_ids
            
    def schedule_render(self, fast: bool = False):
        """Schedule fragment rendering"""
        if fast and (self.is_dragging_fragment or self.is_panning):
            # Fast update during interaction
            if not self.fast_update_timer.isActive():
                self.fast_update_timer.start(16)  # ~60 FPS
        else:
            # Normal rendering
            if not self.render_timer.isActive():
                self.render_timer.start(50)  # 20 FPS for rendering
                
    def render_dirty_fragments(self):
        """Render fragments that need updating"""
        if not self.dirty_fragments:
            return
            
        # Render fragments that need updating
        for fragment_id in list(self.dirty_fragments):
            fragment = self.get_fragment_by_id(fragment_id)
            if fragment and fragment.visible:
                self.render_fragment_pixmap(fragment)
                
        self.dirty_fragments.clear()
        self.update()
        
    def render_fragment_pixmap(self, fragment: Fragment):
        """Render a single fragment to a pixmap"""
        if fragment.image_data is None:
            return
            
        transformed_image = fragment.get_transformed_image()
        if transformed_image is None:
            return
            
        # Don't apply LOD - it causes positioning issues
        # Use the full resolution transformed image
        render_image = transformed_image
        
        # Convert to QPixmap efficiently
        pixmap = self.numpy_to_pixmap(render_image)
        if pixmap:
            self.fragment_pixmaps[fragment.id] = pixmap
            self.fragment_zoom_cache[fragment.id] = self.zoom
            
    def apply_lod(self, image: np.ndarray, zoom: float) -> np.ndarray:
        """Apply level-of-detail scaling"""
        if not self.use_lod or zoom >= self.lod_threshold:
            return image
            
        # Calculate appropriate scale factor
        if zoom < 0.1:
            scale = 0.25
        elif zoom < 0.25:
            scale = 0.5
        else:
            scale = 0.75
            
        height, width = image.shape[:2]
        new_height = max(1, int(height * scale))
        new_width = max(1, int(width * scale))
        
        return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
        
    def numpy_to_pixmap(self, image: np.ndarray) -> Optional[QPixmap]:
        """Convert numpy array to QPixmap efficiently"""
        if image is None or image.size == 0:
            return None
            
        height, width = image.shape[:2]
        
        # Ensure image is in the right format
        if not image.flags['C_CONTIGUOUS']:
            image = np.ascontiguousarray(image)
            
        if len(image.shape) == 3:
            if image.shape[2] == 4:  # RGBA
                bytes_per_line = 4 * width
                format = QImage.Format.Format_RGBA8888
            elif image.shape[2] == 3:  # RGB
                bytes_per_line = 3 * width
                format = QImage.Format.Format_RGB888
            else:
                return None
        else:
            return None
            
        # Create QImage
        q_image = QImage(image.tobytes(), width, height, bytes_per_line, format)
        return QPixmap.fromImage(q_image)
        
    def get_zoom_level(self) -> float:
        """Get quantized zoom level for caching"""
        # Quantize zoom levels to reduce cache misses
        if self.zoom < 0.1:
            return 0.1
        elif self.zoom < 0.25:
            return 0.25
        elif self.zoom < 0.5:
            return 0.5
        elif self.zoom < 1.0:
            return 1.0
        elif self.zoom < 2.0:
            return 2.0
        else:
            return min(self.zoom, 10.0)
            
    def get_fragment_by_id(self, fragment_id: str) -> Optional[Fragment]:
        """Get fragment by ID"""
        for fragment in self.fragments:
            if fragment.id == fragment_id:
                return fragment
        return None
        
    def on_fragment_rendered(self, fragment_id: str, pixmap: QPixmap):
        """Handle completed fragment rendering"""
        self.fragment_pixmaps[fragment_id] = pixmap
        self.update()
        
    def paintEvent(self, event: QPaintEvent):
        """Paint the canvas with optimized rendering"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)  # Disable for performance
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, self.zoom > 2.0)
        
        # Fill background
        painter.fillRect(self.rect(), self.background_color)
        
        if not self.fragments:
            return
            
        # Set up viewport transformation
        painter.save()
        painter.scale(self.zoom, self.zoom)
        painter.translate(self.pan_x, self.pan_y)
        
        # Get visible area for culling
        visible_rect = self.get_visible_world_rect()
        
        # Draw fragments
        for fragment in self.fragments:
            if not fragment.visible:
                continue
                
            # Frustum culling
            if not self.fragment_intersects_rect(fragment, visible_rect):
                continue
                
            self.draw_fragment(painter, fragment)
            
        # Draw selection outlines
        self.draw_selection_outlines(painter)
        
        # Draw group selection outlines
        self.draw_group_selection_outlines(painter)
        
        painter.restore()
        
        # Draw selection rectangle (in screen coordinates)
        if self.is_selecting:
            self.draw_selection_rectangle(painter)
        
    def get_visible_world_rect(self) -> QRect:
        """Get the visible world rectangle for culling"""
        # Convert screen rect to world coordinates
        screen_rect = self.rect()
        
        top_left = self.screen_to_world(screen_rect.topLeft())
        bottom_right = self.screen_to_world(screen_rect.bottomRight())
        
        return QRect(top_left, bottom_right)
        
    def fragment_intersects_rect(self, fragment: Fragment, rect: QRect) -> bool:
        """Check if fragment intersects with the given rectangle"""
        bbox = fragment.get_bounding_box()
        frag_rect = QRect(int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
        return frag_rect.intersects(rect)
        
    def draw_fragment(self, painter: QPainter, fragment: Fragment):
        """Draw a single fragment"""
        pixmap = self.fragment_pixmaps.get(fragment.id)
        if not pixmap:
            # Fragment not rendered yet, mark as dirty and use placeholder
            self.dirty_fragments.add(fragment.id)
            self.schedule_render()
            return
            
        # Apply opacity
        if fragment.opacity < 1.0:
            painter.setOpacity(fragment.opacity)
            
        # Draw the pixmap with precise positioning using QPointF for float coordinates
        painter.drawPixmap(QPointF(fragment.x, fragment.y), pixmap)
        
        # Reset opacity
        if fragment.opacity < 1.0:
            painter.setOpacity(1.0)
            
    def draw_selection_outlines(self, painter: QPainter):
        """Draw selection outlines for fragments"""
        pen = QPen(self.selection_color, self.selection_pen_width / self.zoom)
        painter.setPen(pen)
        painter.setBrush(QBrush())
        
        for fragment in self.fragments:
            if not fragment.visible:
                continue
                
            if fragment.selected or fragment.id == self.selected_fragment_id:
                bbox = fragment.get_bounding_box()
                rect = QRect(int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
                painter.drawRect(rect)
                
    def draw_group_selection_outlines(self, painter: QPainter):
        """Draw group selection outlines for fragments"""
        if not self.selected_fragment_ids:
            return
            
        pen = QPen(self.group_selection_color, self.selection_pen_width / self.zoom)
        painter.setPen(pen)
        painter.setBrush(QBrush())
        
        for fragment in self.fragments:
            if not fragment.visible:
                continue
                
            if fragment.id in self.selected_fragment_ids:
                bbox = fragment.get_bounding_box()
                rect = QRect(int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
                painter.drawRect(rect)
                
    def draw_selection_rectangle(self, painter: QPainter):
        """Draw the selection rectangle"""
        if not self.is_selecting:
            return
            
        painter.save()
        
        # Draw rectangle in screen coordinates
        pen = QPen(self.selection_color, 1)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        
        brush = QBrush(self.selection_rect_color)
        painter.setBrush(brush)
        
        painter.drawRect(self.selection_rect)
        
        painter.restore()
                
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.selection_mode:
                # Start rectangle selection
                self.is_selecting = True
                self.selection_start = event.pos()
                self.selection_current = event.pos()
                self.selection_rect = QRect(self.selection_start, self.selection_current)
            else:
                world_pos = self.screen_to_world(event.pos())
                clicked_fragment = self.get_fragment_at_position(world_pos.x(), world_pos.y())
                
                if clicked_fragment:
                    # Check if clicking on a group-selected fragment
                    if clicked_fragment.id in self.selected_fragment_ids:
                        # Start dragging the entire group
                        self.is_dragging_fragment = True
                        self.dragged_fragment_id = None  # Indicates group drag
                        # Calculate offset for the clicked fragment
                        self.drag_offset = QPoint(
                            int(world_pos.x() - clicked_fragment.x),
                            int(world_pos.y() - clicked_fragment.y)
                        )
                    else:
                        # Select and start dragging single fragment
                        self.fragment_selected.emit(clicked_fragment.id)
                        self.is_dragging_fragment = True
                        self.dragged_fragment_id = clicked_fragment.id
                        self.drag_offset = QPoint(
                            int(world_pos.x() - clicked_fragment.x),
                            int(world_pos.y() - clicked_fragment.y)
                        )
                else:
                    # Clear selections and start panning
                    self.clear_group_selection()
                    self.is_panning = True
                
        elif event.button() == Qt.MouseButton.MiddleButton:
            # Always pan with middle button
            self.is_panning = True
            
        self.last_mouse_pos = event.pos()
        
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move events"""
        if self.is_selecting:
            # Update selection rectangle
            self.selection_current = event.pos()
            self.selection_rect = QRect(self.selection_start, self.selection_current).normalized()
            self.update()
            
        elif self.is_dragging_fragment:
            world_pos = self.screen_to_world(event.pos())
            
            if self.dragged_fragment_id:
                # Move single fragment
                new_x = world_pos.x() - self.drag_offset.x()
                new_y = world_pos.y() - self.drag_offset.y()
                self.fragment_moved.emit(self.dragged_fragment_id, new_x, new_y)
            elif self.selected_fragment_ids:
                # Move group of fragments
                # Calculate movement delta from last position
                if hasattr(self, 'last_drag_pos'):
                    delta_x = world_pos.x() - self.last_drag_pos.x()
                    delta_y = world_pos.y() - self.last_drag_pos.y()
                    
                    # Apply delta to all selected fragments
                    for frag_id in self.selected_fragment_ids:
                        fragment = self.get_fragment_by_id(frag_id)
                        if fragment:
                            new_x = fragment.x + delta_x
                            new_y = fragment.y + delta_y
                            self.fragment_moved.emit(frag_id, new_x, new_y)
                            
                self.last_drag_pos = world_pos
                
            self.update()  # Just update display, don't re-render
            
        elif self.is_panning:
            # Pan viewport
            delta = event.pos() - self.last_mouse_pos
            self.pan_x += delta.x() / self.zoom
            self.pan_y += delta.y() / self.zoom
            self.viewport_changed.emit(self.zoom, self.pan_x, self.pan_y)
            self.update()
            
        self.last_mouse_pos = event.pos()
        
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release events"""
        if self.is_selecting:
            # Complete rectangle selection
            self.is_selecting = False
            selected_ids = self.get_fragments_in_rect(self.selection_rect)
            if selected_ids:
                self.add_to_group_selection(selected_ids)
            self.update()
            
        self.is_panning = False
        if self.is_dragging_fragment:
            self.is_dragging_fragment = False
            self.dragged_fragment_id = None
            if hasattr(self, 'last_drag_pos'):
                delattr(self, 'last_drag_pos')
        
    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel events for zooming"""
        # Get mouse position in world coordinates before zoom
        mouse_world_before = self.screen_to_world(event.position().toPoint())
        
        # Calculate zoom factor
        zoom_factor = 1.2 if event.angleDelta().y() > 0 else 1.0 / 1.2
        new_zoom = np.clip(self.zoom * zoom_factor, self.min_zoom, self.max_zoom)
        
        if new_zoom != self.zoom:
            self.zoom = new_zoom
            
            # Adjust pan to keep mouse position fixed
            mouse_world_after = self.screen_to_world(event.position().toPoint())
            self.pan_x += float(mouse_world_before.x() - mouse_world_after.x())
            self.pan_y += float(mouse_world_before.y() - mouse_world_after.y())
            
            # Just update the display - don't re-render fragments for zoom changes
            self.update()
            
            self.viewport_changed.emit(self.zoom, self.pan_x, self.pan_y)
            
    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press events"""
        if event.key() == Qt.Key.Key_Delete and self.selected_fragment_id:
            self.delete_requested.emit(self.selected_fragment_id)
        elif event.key() == Qt.Key.Key_Delete and self.selected_fragment_ids:
            # Delete all selected fragments
            for frag_id in self.selected_fragment_ids:
                self.delete_requested.emit(frag_id)
        elif event.key() == Qt.Key.Key_Escape:
            # Clear selections
            self.clear_group_selection()
            self.set_selection_mode(False)
        else:
            super().keyPressEvent(event)
        
    def resizeEvent(self, event: QResizeEvent):
        """Handle resize events"""
        super().resizeEvent(event)
        self.update()
        
    def screen_to_world(self, screen_pos: QPoint) -> QPoint:
        """Convert screen coordinates to world coordinates"""
        world_x = (screen_pos.x() / self.zoom) - self.pan_x
        world_y = (screen_pos.y() / self.zoom) - self.pan_y
        return QPoint(int(world_x), int(world_y))
        
    def world_to_screen(self, world_pos: QPoint) -> QPoint:
        """Convert world coordinates to screen coordinates"""
        screen_x = (world_pos.x() + self.pan_x) * self.zoom
        screen_y = (world_pos.y() + self.pan_y) * self.zoom
        return QPoint(int(screen_x), int(screen_y))
        
    def get_fragment_at_position(self, x: float, y: float) -> Optional[Fragment]:
        """Get the topmost fragment at the given position"""
        # Check fragments in reverse order (top to bottom)
        for fragment in reversed(self.fragments):
            if fragment.visible and fragment.contains_point(x, y):
                return fragment
        return None
        
    def zoom_to_fit(self):
        """Zoom to fit all visible fragments"""
        visible_fragments = [f for f in self.fragments if f.visible and f.image_data is not None]
        if not visible_fragments:
            return
            
        # Calculate bounds
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')
        
        for fragment in visible_fragments:
            bbox = fragment.get_bounding_box()
            min_x = min(min_x, bbox[0])
            min_y = min(min_y, bbox[1])
            max_x = max(max_x, bbox[0] + bbox[2])
            max_y = max(max_y, bbox[1] + bbox[3])
            
        content_width = max_x - min_x
        content_height = max_y - min_y
        
        if content_width <= 0 or content_height <= 0:
            return
            
        # Calculate zoom to fit with padding
        widget_width = self.width()
        widget_height = self.height()
        
        zoom_x = widget_width / content_width
        zoom_y = widget_height / content_height
        self.zoom = min(zoom_x, zoom_y) * 0.9  # 90% to add padding
        
        # Center the content
        content_center_x = (min_x + max_x) / 2
        content_center_y = (min_y + max_y) / 2
        
        self.pan_x = (widget_width / 2 / self.zoom) - content_center_x
        self.pan_y = (widget_height / 2 / self.zoom) - content_center_y
        
        self.viewport_changed.emit(self.zoom, self.pan_x, self.pan_y)
        self.update()
        
    def zoom_to_100(self):
        """Reset zoom to 100%"""
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        
        self.viewport_changed.emit(self.zoom, self.pan_x, self.pan_y)
        self.update()
        
    def invalidate_fragment(self, fragment_id: str):
        """Mark a fragment as needing re-rendering"""
        self.dirty_fragments.add(fragment_id)
        self.fragment_pixmaps.pop(fragment_id, None)
        self.fragment_zoom_cache.pop(fragment_id, None)
        self.schedule_render()
        
    def clear_cache(self):
        """Clear all cached pixmaps"""
        self.fragment_pixmaps.clear()
        self.fragment_zoom_cache.clear()
        self.dirty_fragments.update(f.id for f in self.fragments if f.visible)
        self.schedule_render()
        
    def force_refresh(self):
        """Force refresh of all fragments"""
        self.clear_cache()
        self.update()
        
    def apply_group_transform(self, fragment_ids: List[str], transform_type: str, value=None):
        """Apply transformation to a group of fragments"""
        if transform_type == 'rotate_cw':
            # Calculate group center
            center_x, center_y = self.calculate_group_center(fragment_ids)
            
            # Rotate each fragment around the group center
            for fragment_id in fragment_ids:
                fragment = self.get_fragment_by_id(fragment_id)
                if fragment:
                    # Rotate fragment's own rotation
                    fragment.rotation = (fragment.rotation + 90) % 360.0
                    fragment.invalidate_cache()
                    
                    # Rotate position around group center
                    dx = fragment.x - center_x
                    dy = fragment.y - center_y
                    
                    # 90-degree rotation: (x, y) -> (-y, x)
                    new_dx = -dy
                    new_dy = dx
                    
                    fragment.x = center_x + new_dx
                    fragment.y = center_y + new_dy
                    
        elif transform_type == 'rotate_ccw':
            # Calculate group center
            center_x, center_y = self.calculate_group_center(fragment_ids)
            
            # Rotate each fragment around the group center
            for fragment_id in fragment_ids:
                fragment = self.get_fragment_by_id(fragment_id)
                if fragment:
                    # Rotate fragment's own rotation
                    fragment.rotation = (fragment.rotation - 90) % 360.0
                    fragment.invalidate_cache()
                    
                    # Rotate position around group center
                    dx = fragment.x - center_x
                    dy = fragment.y - center_y
                    
                    # -90-degree rotation: (x, y) -> (y, -x)
                    new_dx = dy
                    new_dy = -dx
                    
                    fragment.x = center_x + new_dx
                    fragment.y = center_y + new_dy
                    
        elif transform_type == 'rotate_angle':
            # Calculate group center
            center_x, center_y = self.calculate_group_center(fragment_ids)
            angle = value
            
            # Rotate each fragment around the group center
            for fragment_id in fragment_ids:
                fragment = self.get_fragment_by_id(fragment_id)
                if fragment:
                    # Rotate fragment's own rotation
                    fragment.rotation = (fragment.rotation + angle) % 360.0
                    fragment.invalidate_cache()
                    
                    # Rotate position around group center
                    dx = fragment.x - center_x
                    dy = fragment.y - center_y
                    
                    # Arbitrary angle rotation
                    angle_rad = np.radians(angle)
                    cos_a = np.cos(angle_rad)
                    sin_a = np.sin(angle_rad)
                    
                    new_dx = dx * cos_a - dy * sin_a
                    new_dy = dx * sin_a + dy * cos_a
                    
                    fragment.x = center_x + new_dx
                    fragment.y = center_y + new_dy
                    
        elif transform_type == 'flip_horizontal':
            # Calculate group center
            center_x, center_y = self.calculate_group_center(fragment_ids)
            
            for fragment_id in fragment_ids:
                fragment = self.get_fragment_by_id(fragment_id)
                if fragment:
                    # Flip fragment itself
                    fragment.flip_horizontal = not fragment.flip_horizontal
                    fragment.invalidate_cache()
                    
                    # Mirror position around group center
                    dx = fragment.x - center_x
                    fragment.x = center_x - dx
                    
        elif transform_type == 'flip_vertical':
            # Calculate group center
            center_x, center_y = self.calculate_group_center(fragment_ids)
            
            for fragment_id in fragment_ids:
                fragment = self.get_fragment_by_id(fragment_id)
                if fragment:
                    # Flip fragment itself
                    fragment.flip_vertical = not fragment.flip_vertical
                    fragment.invalidate_cache()
                    
                    # Mirror position around group center
                    dy = fragment.y - center_y
                    fragment.y = center_y - dy
                    
        elif transform_type == 'translate':
            dx, dy = value
            for fragment_id in fragment_ids:
                fragment = self.get_fragment_by_id(fragment_id)
                if fragment:
                    fragment.x += dx
                    fragment.y += dy
                    
        # Mark all fragments as dirty and update immediately
        for fragment_id in fragment_ids:
            self.dirty_fragments.add(fragment_id)
            
        self.schedule_render(fast=True)
        
    def calculate_group_center(self, fragment_ids: List[str]) -> Tuple[float, float]:
        """Calculate the center point of a group of fragments"""
        if not fragment_ids:
            return (0.0, 0.0)
            
        total_x = 0.0
        total_y = 0.0
        count = 0
        
        for fragment_id in fragment_ids:
            fragment = self.get_fragment_by_id(fragment_id)
            if fragment:
                bbox = fragment.get_bounding_box()
                # Use center of fragment
                center_x = bbox[0] + bbox[2] / 2
                center_y = bbox[1] + bbox[3] / 2
                total_x += center_x
                total_y += center_y
                count += 1
                
        if count > 0:
            return (total_x / count, total_y / count)
        else:
            return (0.0, 0.0)