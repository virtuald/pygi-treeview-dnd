pygi-treeview-dnd
=================

GTK+ provides a `high-level DnD API <https://developer.gnome.org/gtk3/stable/gtk3-GtkTreeView-drag-and-drop.html>`_
that makes implementing drag and drop on TreeView objects (lists, trees, etc)
significantly easier, and far less error prone. There are hundreds of lines of
code in GTK to implement this -- so 

Unfortunately, there's a longstanding bug in PyGObject that prevents python
programs from using this API. `See the bug report for details <https://bugzilla.gnome.org/show_bug.cgi?id=756072>`,
but basically the SelectionData in drag_data_get is a copy instead of the exact
same SelectionData object, and GTK expects you to modify the original object.

This is a workaround that uses some metaclass magic, GTK internals, and ctypes
to patch up custom TreeStore/ListStore objects. It seems to work, and I plan
on using it extensively in Exaile. If it doesn't work well or if there are
issues, then I'll post a note on github.

Ideally, one day PyGObject will have a fix for this issue, and this package
will no longer be necessary.

Installation
============

This project is easily installed via pip:

    pip install pygi-treeview-dnd

Requirements
============

* GTK+ 3.x and PyGObject 3.x
* Currently only tested on Linux, GTK+ 3.20, and Python 2.7

Usage
=====

See `examples` on the github repo for simple examples.

Author
======

Dustin Spicuzza (dustin@virtualroadside.com)

License
=======

LGPL 2.1+ (Same as PyGI)