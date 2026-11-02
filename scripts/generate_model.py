"""Generate our original primitive RAL-6 URDF. No third-party model assets."""

from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, indent, tostring

ROOT = Path(__file__).resolve().parents[1]
robot = Element("robot", name="RAL-6")


def link(name: str, size: str, xyz: str, color: str) -> None:
    item = SubElement(robot, "link", name=name)
    inertial = SubElement(item, "inertial")
    SubElement(inertial, "origin", xyz=xyz)
    SubElement(inertial, "mass", value="1")
    SubElement(inertial, "inertia", ixx="0.01", ixy="0", ixz="0", iyy="0.01", iyz="0", izz="0.01")
    for tag in ("visual", "collision"):
        part = SubElement(item, tag)
        SubElement(part, "origin", xyz=xyz)
        geometry = SubElement(part, "geometry")
        SubElement(geometry, "box", size=size)
        if tag == "visual":
            material = SubElement(part, "material", name=name + "_color")
            SubElement(material, "color", rgba=color)


link("base", ".22 .22 .18", "0 0 .09", ".12 .16 .22 1")
sizes = [
    ".09 .09 .15",
    ".31 .065 .065",
    ".27 .06 .06",
    ".09 .055 .055",
    ".09 .05 .05",
    ".12 .04 .04",
]
centers = ["0 0 .08", ".16 0 0", ".14 0 0", ".05 0 0", ".05 0 0", ".06 0 0"]
origins = ["0 0 .18", "0 0 .16", ".32 0 0", ".28 0 0", ".10 0 0", ".10 0 0"]
axes = ["0 0 1", "0 1 0", "0 1 0", "1 0 0", "0 1 0", "1 0 0"]
limits = [
    2.9670597283903604,
    1.9198621771937625,
    2.356194490192345,
    3.141592653589793,
    2.0943951023931953,
    3.141592653589793,
]
for i in range(6):
    link(f"link{i + 1}", sizes[i], centers[i], ".94 .52 .13 1" if i % 2 == 0 else ".23 .32 .43 1")
    joint = SubElement(robot, "joint", name=f"joint{i + 1}", type="revolute")
    SubElement(joint, "parent", link="base" if i == 0 else f"link{i}")
    SubElement(joint, "child", link=f"link{i + 1}")
    SubElement(joint, "origin", xyz=origins[i], rpy="0 0 0")
    SubElement(joint, "axis", xyz=axes[i])
    SubElement(
        joint, "limit", lower=str(-limits[i]), upper=str(limits[i]), effort="100", velocity="2"
    )
link("tcp", ".012 .055 .055", "0 0 0", ".1 .85 .76 1")
tool = SubElement(robot, "joint", name="tool_fixed", type="fixed")
SubElement(tool, "parent", link="link6")
SubElement(tool, "child", link="tcp")
SubElement(tool, "origin", xyz=".12 0 0", rpy="0 0 0")
indent(robot)
(ROOT / "src/robotarm_lab/assets/ral6.urdf").write_text(
    '<?xml version="1.0"?>\n' + tostring(robot, encoding="unicode") + "\n", encoding="utf-8"
)
