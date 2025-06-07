"""Writing the finished toolpath in whatever language the machine speaks.

Every post is a pure function from a toolpath to text. None of them decides
anything about the cut, so a plate posted two ways is the same plate.
"""

from dragpoint.post import iso as _iso
from dragpoint.post.base import PostOptions, post_names, render

__all__ = ["PostOptions", "post_names", "render"]

# Importing the post modules is what puts them in the register.
_POST_MODULES = (_iso,)
