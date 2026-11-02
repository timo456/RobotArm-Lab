"""Qt-resolved OpenGL renderer, including the Windows software OpenGL 3.0 path."""

from collections import deque
from time import perf_counter

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QMatrix4x4
from PySide6.QtOpenGL import (
    QOpenGLBuffer,
    QOpenGLFunctions_3_0,
    QOpenGLFunctions_3_3_Core,
    QOpenGLShader,
    QOpenGLShaderProgram,
    QOpenGLVertexArrayObject,
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from ..model import HOME
from .geometry import (
    MESHES,
    collision_parts,
    environment_parts,
    link_frames,
    robot_parts,
    transform,
)


class GL:
    """Standard OpenGL tokens; function resolution stays with Qt's active context."""

    GL_FLOAT = 0x1406
    GL_RENDERER = 0x1F01
    GL_VERSION = 0x1F02
    GL_TRIANGLES = 0x0004
    GL_LINES = 0x0001
    GL_LINE_STRIP = 0x0003
    GL_COLOR_BUFFER_BIT = 0x4000
    GL_DEPTH_BUFFER_BIT = 0x0100
    GL_DEPTH_TEST = 0x0B71
    GL_MULTISAMPLE = 0x809D
    GL_BLEND = 0x0BE2
    GL_SRC_ALPHA = 0x0302
    GL_ONE_MINUS_SRC_ALPHA = 0x0303
    GL_CULL_FACE = 0x0B44
    GL_FRONT_AND_BACK = 0x0408
    GL_LINE = 0x1B01
    GL_FILL = 0x1B02


VERTEX = """#version 130
in vec3 position;
in vec3 normal;
uniform mat4 model, viewProjection;
uniform mat4 normalMatrix;
uniform bool shadow;
out vec3 worldPosition, worldNormal;
void main() {
    vec4 p=model*vec4(position,1.0);
    worldNormal=mat3(normalMatrix)*normal;
    if(shadow) { p.xy-=p.z*vec2(-0.65,-0.85); p.z=0.004; }
    worldPosition=p.xyz;
    gl_Position=viewProjection*p;
}
"""
FRAGMENT = """#version 130
in vec3 worldPosition, worldNormal;
uniform vec4 baseColor;
uniform vec3 eye;
uniform float metal;
uniform bool unlit, shadow;
out vec4 color;
void main() {
    if(unlit || shadow) { color=baseColor; return; }
    vec3 n=normalize(worldNormal), v=normalize(eye-worldPosition);
    vec3 l=normalize(vec3(-0.65,-0.85,1.0));
    float key=max(dot(n,l),0.0), fill=max(dot(n,normalize(vec3(1,1,0.4))),0.0);
    float spec=pow(max(dot(n,normalize(v+l)),0.0),40.0)*(0.12+metal*0.65);
    float rim=pow(1.0-max(dot(n,v),0.0),3.0)*0.10;
    vec3 c=baseColor.rgb*(0.32+0.65*key+0.18*fill)+vec3(spec+rim);
    color=vec4(c,baseColor.a);
}
"""


def look_at(eye, target):
    z = eye - target
    z /= np.linalg.norm(z)
    x = np.cross([0, 0, 1], z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    m = np.eye(4)
    m[:3, :3] = [x, y, z]
    m[:3, 3] = -m[:3, :3] @ eye
    return m


def perspective(aspect):
    f, near, far = 1 / np.tan(np.deg2rad(42) / 2), 0.025, 40
    m = np.zeros((4, 4))
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = 2 * far * near / (near - far)
    m[3, 2] = -1
    return m


class Viewport(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("viewport")
        self.setMinimumSize(320, 240)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.snapshot = None
        self.preview_fraction = 1.0
        self.show_proxies = False
        self.show_path = True
        self.show_axes = True
        self.parts, self.environment = robot_parts(), environment_parts()
        self.proxies = collision_parts()
        self.resources = {}
        self.program = None
        self.renderer_info = "Initializing OpenGL"
        self.error = ""
        self.frame_times, self.render_times = deque(maxlen=4096), deque(maxlen=4096)
        self.frameSwapped.connect(lambda: self.frame_times.append(perf_counter()))
        self.trail = deque(maxlen=2048)
        self.mouse = None
        self.reset_camera()

    def reset_camera(self):
        self.yaw, self.elevation, self.distance = -65.0, 24.0, 1.55
        self.target = np.array([0.39, 0, 0.30])
        self.update()

    def initializeGL(self):
        try:
            fmt = self.context().format()
            version = (fmt.majorVersion(), fmt.minorVersion())
            self.gl = QOpenGLFunctions_3_3_Core() if version >= (3, 3) else QOpenGLFunctions_3_0()
            if not self.gl.initializeOpenGLFunctions():
                raise RuntimeError("OpenGL 3.0 or newer is required")
            self.program = QOpenGLShaderProgram(self)
            for kind, source in (
                (QOpenGLShader.ShaderTypeBit.Vertex, VERTEX),
                (QOpenGLShader.ShaderTypeBit.Fragment, FRAGMENT),
            ):
                if not self.program.addShaderFromSourceCode(kind, source):
                    raise RuntimeError(self.program.log())
            self.program.bindAttributeLocation("position", 0)
            self.program.bindAttributeLocation("normal", 1)
            if not self.program.link():
                raise RuntimeError(self.program.log())
            self.program.bind()
            self.uniforms = {
                n: self.program.uniformLocation(n)
                for n in (
                    "model",
                    "normalMatrix",
                    "viewProjection",
                    "baseColor",
                    "metal",
                    "eye",
                    "unlit",
                    "shadow",
                )
            }
            for name, data in MESHES.items():
                self.resources[name] = self.upload(data)
            self.line_vao, self.line_vbo, _ = self.upload(np.zeros((2, 6), dtype=np.float32))
            self.line_vbo.setUsagePattern(QOpenGLBuffer.UsagePattern.DynamicDraw)
            self.renderer_info = (
                self.gl.glGetString(GL.GL_RENDERER) + " / " + self.gl.glGetString(GL.GL_VERSION)
            )
            self.context().aboutToBeDestroyed.connect(self.release)
        except Exception as exc:
            self.error = f"OpenGL initialization failed: {exc}"

    def upload(self, data):
        vao = QOpenGLVertexArrayObject(self)
        if not vao.create():
            raise RuntimeError("Unable to allocate a vertex array")
        vao.bind()
        vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        if not vbo.create():
            vao.destroy()
            raise RuntimeError("Unable to allocate a vertex buffer")
        vbo.bind()
        vbo.allocate(data.tobytes(), data.nbytes)
        for index, offset in ((0, 0), (1, 12)):
            self.program.enableAttributeArray(index)
            self.program.setAttributeBuffer(index, GL.GL_FLOAT, offset, 3, 24)
        return vao, vbo, len(data)

    def release(self):
        self.makeCurrent()
        for vao, vbo, _ in self.resources.values():
            vbo.destroy()
            vao.destroy()
        self.resources.clear()
        if hasattr(self, "line_vbo"):
            self.line_vbo.destroy()
            self.line_vao.destroy()
            del self.line_vbo
        if self.program:
            self.program.removeAllShaders()
            self.program.deleteLater()
            self.program = None
        self.doneCurrent()

    def set_snapshot(self, snapshot):
        self.snapshot = snapshot
        point = snapshot.tcp[:3]
        if snapshot.state == "RUNNING" and (
            not self.trail or np.linalg.norm(np.array(point) - self.trail[-1]) > 0.001
        ):
            self.trail.append(point)
        self.update()

    def matrix(self, name, value):
        self.program.setUniformValue(
            self.uniforms[name], QMatrix4x4(*np.asarray(value).ravel().tolist())
        )

    def draw_part(self, part, frames=None, color=None):
        matrix = part.local if part.frame < 0 or frames is None else frames[part.frame] @ part.local
        self.matrix("model", matrix)
        normal = np.eye(4)
        normal[:3, :3] = np.linalg.inv(matrix[:3, :3]).T
        self.matrix("normalMatrix", normal)
        rgba = color if color is not None else (*part.color, 1)
        self.gl.glUniform4f(self.uniforms["baseColor"], *rgba)
        self.gl.glUniform1f(self.uniforms["metal"], part.metal)
        vao, _, count = self.resources[part.mesh]
        vao.bind()
        self.gl.glDrawArrays(GL.GL_TRIANGLES, 0, count)

    def lines(self, positions, color, strip=False):
        if len(positions) < 2:
            return
        data = np.zeros((len(positions), 6), dtype=np.float32)
        data[:, :3] = positions
        self.line_vao.bind()
        self.line_vbo.bind()
        self.line_vbo.allocate(data.tobytes(), data.nbytes)
        self.matrix("model", np.eye(4))
        self.gl.glUniform1i(self.uniforms["unlit"], 1)
        self.gl.glUniform4f(self.uniforms["baseColor"], *color)
        self.gl.glDrawArrays(GL.GL_LINE_STRIP if strip else GL.GL_LINES, 0, len(data))
        self.gl.glUniform1i(self.uniforms["unlit"], 0)

    def paintGL(self):
        start = perf_counter()
        if self.program is None or self.error:
            return
        try:
            self.gl.glClearColor(0.055, 0.083, 0.105, 1)
            self.gl.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
            self.gl.glEnable(GL.GL_DEPTH_TEST)
            self.gl.glEnable(GL.GL_MULTISAMPLE)
            self.gl.glEnable(GL.GL_BLEND)
            self.gl.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
            self.gl.glDisable(GL.GL_CULL_FACE)
            self.gl.glDepthMask(True)
            self.gl.glUseProgram(self.program.programId())
            self.gl.glUniform1i(self.uniforms["unlit"], 0)
            self.gl.glUniform1i(self.uniforms["shadow"], 0)
            yaw, elevation = np.deg2rad([self.yaw, self.elevation])
            aspect = self.width() / max(1, self.height())
            distance = self.distance * min(1.0, max(0.68, 1.8 / aspect))
            eye = self.target + distance * np.array(
                [
                    np.cos(yaw) * np.cos(elevation),
                    np.sin(yaw) * np.cos(elevation),
                    np.sin(elevation),
                ]
            )
            self.matrix(
                "viewProjection",
                perspective(self.width() / max(1, self.height())) @ look_at(eye, self.target),
            )
            self.gl.glUniform3f(self.uniforms["eye"], *eye)
            for part in self.environment:
                self.draw_part(part)
            grid = []
            for x in np.arange(-0.6, 1.21, 0.1):
                grid.extend([[x, -0.7, 0.001], [x, 0.7, 0.001]])
            for y in np.arange(-0.7, 0.71, 0.1):
                grid.extend([[-0.65, y, 0.001], [1.22, y, 0.001]])
            self.lines(grid, (0.29, 0.38, 0.43, 0.32))
            frames = link_frames(self.snapshot.q if self.snapshot else HOME)
            self.gl.glUniform1i(self.uniforms["shadow"], 1)
            self.gl.glDepthMask(False)
            for part in self.parts:
                self.draw_part(part, frames, (0, 0, 0, 0.11))
            self.gl.glUniform1i(self.uniforms["shadow"], 0)
            self.gl.glDepthMask(True)
            for part in self.parts:
                self.draw_part(part, frames)
            if self.snapshot:
                for _, center, half in self.snapshot.obstacles:
                    from .geometry import Part

                    self.draw_part(
                        Part(
                            "box",
                            -1,
                            transform(center, np.array(half) * 2),
                            (0.83, 0.22, 0.24),
                            0.1,
                        )
                    )
                if self.show_path:
                    self.lines(self.trail, (0.20, 0.75, 0.7, 0.65), True)
                    self.lines(self.snapshot.preview_path, (1, 0.72, 0.28, 1), True)
                if self.snapshot.preview and self.snapshot.state != "RUNNING":
                    q = self.snapshot.preview.sample(
                        self.snapshot.preview.duration * self.preview_fraction
                    )[0]
                    ghost = link_frames(q)
                    self.gl.glDepthMask(False)
                    for part in self.parts:
                        if part.frame >= 0:
                            self.draw_part(part, ghost, (0.18, 0.86, 0.81, 0.18))
                    self.gl.glDepthMask(True)
            if self.show_proxies:
                self.gl.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_LINE)
                for part in self.proxies:
                    self.draw_part(part, frames, (0.15, 0.98, 0.78, 0.8))
                self.gl.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_FILL)
            if self.show_axes:
                for frame, length in ((np.eye(4), 0.14), (frames[6], 0.09)):
                    for axis, color in enumerate(
                        ((0.98, 0.3, 0.33, 1), (0.3, 0.9, 0.55, 1), (0.34, 0.64, 1, 1))
                    ):
                        self.lines([frame[:3, 3], frame[:3, 3] + frame[:3, axis] * length], color)
            self.gl.glBindVertexArray(0)
            self.gl.glUseProgram(0)
            self.render_times.append((perf_counter() - start) * 1000)
        except Exception as exc:
            self.error = f"Render failure: {exc}"

    def mousePressEvent(self, event):
        self.mouse = event.position()
        self.setFocus()

    def mouseMoveEvent(self, event):
        if self.mouse is None:
            return
        delta = event.position() - self.mouse
        self.mouse = event.position()
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.yaw -= delta.x() * 0.35
            self.elevation = float(np.clip(self.elevation + delta.y() * 0.25, 5, 85))
        elif event.buttons() & (Qt.MouseButton.RightButton | Qt.MouseButton.MiddleButton):
            yaw = np.deg2rad(self.yaw)
            self.target += (
                self.distance
                * 0.0015
                * (
                    -delta.x() * np.array([-np.sin(yaw), np.cos(yaw), 0])
                    + delta.y() * np.array([0, 0, 1])
                )
            )
        self.update()

    def mouseReleaseEvent(self, event):
        self.mouse = None

    def wheelEvent(self, event):
        self.distance = float(
            np.clip(self.distance * np.exp(-event.angleDelta().y() / 1200), 0.65, 8)
        )
        self.update()

    @property
    def fps(self):
        recent = [t for t in self.frame_times if t > perf_counter() - 2]
        return (len(recent) - 1) / (recent[-1] - recent[0]) if len(recent) > 1 else 0.0
