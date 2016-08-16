#!/usr/bin/env python
#
# This sample program should be executed like so:
#
#    python treetest.py ~/some/path/*
#
# And it will display the files in the treeview.
#

from __future__ import print_function

# This is only required to make the example with without requiring installation
# - Most of the time, you shouldn't use this hack
import sys
from os.path import join, dirname
sys.path.insert(0, join(dirname(__file__), '..'))

import os.path

import gi
gi.require_version('Gdk', '3.0')
gi.require_version('Gtk', '3.0')

from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import GObject

from gi_treeviewdnd import PatchedListStore


class MyTreeView(Gtk.TreeView):
    '''
        TreeView that enables using the high level DnD API
    '''
    
    def __init__(self, args):
        Gtk.TreeView.__init__(self)
        
        self.model = MyTreeViewModel(GObject.TYPE_STRING, GObject.TYPE_STRING)
        self.set_model(self.model)
        
        self.append_column(Gtk.TreeViewColumn('name', Gtk.CellRendererText(), text=0))
        
        targets = [
            ('text/plain', 0, 0)
        ]
        
        self.enable_model_drag_source(Gdk.ModifierType.BUTTON1_MASK,
                                      targets,
                                      Gdk.DragAction.MOVE)
        
        self.enable_model_drag_dest(targets,
                                    Gdk.DragAction.MOVE)
    
        for row in args:
            self.model.append(row)


class MyTreeViewModel(PatchedListStore):
    '''
        Custom ListStore that implements GTK+ high level DnD via the
        TreeDragSource and TreeDragDest interfaces
    '''

    #
    # TreeDragSource
    #
    
    def do_drag_data_get(self, path, selection_data):
        print('MyTreeViewModel.do_drag_data_get', selection_data)
        uri = self[path][1]
        print('- setting uri        ', uri)
        selection_data.set_text(uri, -1)
        return True
    
    def do_row_draggable(self, path):
        print('do_row_draggable', path)
        return True
    
    
    def do_drag_data_delete(self, path):
        print('do_drag_data_delete', path)
        del self[path]
        return True
    
    #
    # TreeDragDest interface
    #
    
    def do_drag_data_received(self, dest_path, selection_data):
        print('MyTreeViewModel.do_drag_data_received')
        received_data = selection_data.get_text()
        
        print('-', received_data)
        
        idx = dest_path.get_indices()[0]
        self.insert(idx, row=(os.path.basename(received_data), received_data))
        
        return True
    
    def do_row_drop_possible(self, dest_path, selection_data):
        print('is possible?')
        return True
    

if __name__ == '__main__':
    
    args = []
    
    #
    # Grab file arguments to put into TreeView
    #
    
    import glob
    
    def do(a):
        args.append((os.path.basename(a), Gio.File.new_for_commandline_arg(a).get_uri()))
    
    for arg in sys.argv[1:]:
        if '*' in arg:
            for a in glob.glob(arg):
                do(a)
        else:
            do(arg)
    
    #
    # Construct demo window
    #
    
    window = Gtk.Window.new(Gtk.WindowType.TOPLEVEL)
    
    sw = Gtk.ScrolledWindow.new()
    tv = MyTreeView(args)
    sw.add(tv)
            
    window.add(sw)
    window.connect('destroy', Gtk.main_quit)
    
    window.set_default_size(400, 300)
    
    window.show_all()
    
    #import sigint
    #with sigint.InterruptibleLoopContext(Gtk.main_quit):
    
    Gtk.main()
