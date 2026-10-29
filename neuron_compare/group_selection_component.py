"""Interactive group assignment grid.

Streamlit's st.checkbox does not expose Shift-key events, so this component
uses a small HTML/JavaScript table. Values are delivered to Streamlit via
the custom-component protocol. File IDs are never derived from filenames.
"""
import json
import streamlit.components.v1 as components

_COMPONENT = components.declare_component(
    "pcap_group_grid", path=__import__("os").path.join(__import__("os").path.dirname(__file__), "group_grid")
)


def group_selection_grid(files, assignments, group_names, sort_mode="Upload order", key="group_grid"):
    """Render checkbox matrix and return {file_id: selected group index or -1}.

    Alt/shift mouse range selections are handled in the browser, then the
    component returns the full state. Streamlit receives a plain dictionary.
    """
    return _COMPONENT(
        files=files,
        assignments=assignments,
        groups=group_names,
        sort_mode=sort_mode,
        key=key,
        default=assignments,
    )
