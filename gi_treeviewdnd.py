#
# Copyright (C) 2016 Dustin Spicuzza <dustin@virtualroadside.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301
# USA

import ctypes

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GIRepository', '2.0')

from gi.types import GObjectMeta

from gi.repository import GIRepository
from gi.repository import Gtk
from gi.repository import GObject

__all__ = ['TreeDragSourceMeta', 'PatchedListStore', 'PatchedTreeStore']

# Load the libraries we need via GIRepository
def _get_shared_library(n):
    repo = GIRepository.Repository.get_default()
    return repo.get_shared_library(n).split(',')[0]

def _fn(dll, name, args, res=None):
    fn = getattr(dll, name)
    fn.restype = res
    fn.argtypes = args
    return fn

_gobject_dll = ctypes.CDLL(_get_shared_library('GObject'))
_gtk_dll = ctypes.CDLL(_get_shared_library('Gtk'))

g_value_set_object =                    _fn(_gobject_dll, 'g_value_set_object',
                                            (ctypes.c_void_p, ctypes.c_void_p))
                                            
g_value_set_static_boxed =              _fn(_gobject_dll, 'g_value_set_static_boxed',
                                            (ctypes.c_void_p, ctypes.c_void_p))

gtk_selection_data_get_data_type =      _fn(_gtk_dll, 'gtk_selection_data_get_data_type',
                                            (ctypes.c_void_p,), ctypes.c_void_p)

gtk_selection_data_set =                _fn(_gtk_dll, 'gtk_selection_data_set',
                                            (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_int))

_drag_data_get_func = ctypes.CFUNCTYPE(ctypes.c_bool,
                                       ctypes.c_void_p,
                                       ctypes.c_void_p,
                                       ctypes.c_void_p)

def create_drag_data_get_thunk(cls):
    '''
        Constructs a custom thunk function for each class
    
        This is in a closure so that we can use the class to construct a
        GObject.Value for converting the widget object
    '''
    
    def _drag_data_get(raw_widget, raw_path, raw_selection_data):
        '''
            Static function that gets inserted as the drag_data_get vfunction,
            instead of using the vfunction implementation provided by pygobject
            
            This function exists so that we can modify the raw selection data
            explicitly, which allows the high-level DnD API to work.
        '''
        
        # It turns out that GValue is really useful for converting raw pointers
        # to/from python objects. We use it + ctypes to xform the values
        
        # Grab the python wrapper for the widget instance
        gv = GObject.Value(cls)
        g_value_set_object(hash(gv), raw_widget)
        widget = gv.get_object()
        
        # Convert the path to a python object via GValue
        v1 = GObject.Value(Gtk.TreePath)
        g_value_set_static_boxed(ctypes.c_void_p(hash(v1)), raw_path)
        path = v1.get_boxed()

        # Convert the selection data too
        v2 = GObject.Value(Gtk.SelectionData)
        g_value_set_static_boxed(ctypes.c_void_p(hash(v2)), raw_selection_data)
        selection_data = v2.get_boxed()
        
        # Call the original virtual function with the converted arguments
        retval = widget.do_drag_data_get(path, selection_data)
        
        # At this point, selection_data has the information, but it's still just
        # a copy. Copy the data back to the original selection data
        data = selection_data.get_data()
        gtk_selection_data_set(raw_selection_data,
                               gtk_selection_data_get_data_type(hash(selection_data)),
                               selection_data.get_format(),
                               data, len(data))
        
        return retval

    return _drag_data_get_func(_drag_data_get)


def vfunc_info_get_address(vfunc_info, gtype):
    '''
        GIRepository.vfunc_info_get_address almost does what we need... but it
        derefs the address, so it cannot be used for our purposes. This code is
        a translation of that C code into python
    '''
    container_info = vfunc_info.get_container()
    if container_info.get_type() == GIRepository.InfoType.OBJECT:
        object_info = container_info
        interface_info = None
        struct_info = GIRepository.object_info_get_class_struct(object_info)
    else:
        interface_info = container_info
        object_info = None
        struct_info = GIRepository.interface_info_get_iface_struct(interface_info)
        
    field_info = GIRepository.struct_info_find_field(struct_info, vfunc_info.get_name())
    if field_info is None:
        raise AttributeError("Could not find struct field for vfunc")
    
    implementor_class = GObject.type_class_ref(gtype)
    if object_info:
        implementor_vtable = implementor_class
    else:
        interface_type = GIRepository.registered_type_info_get_g_type(interface_info)
        implementor_vtable = GObject.type_interface_peek(implementor_class, interface_type)
    
    offset = GIRepository.field_info_get_offset(field_info)
    return hash(implementor_vtable) + offset


class TreeDragSourceMeta(GObjectMeta):
    '''
        Metaclass you can use to patch TreeDragSource.drag_data_get so that it
        works correctly in a python program.
        
        .. note:: Most users will prefer to use PatchedListStore and
                  PatchedTreeStore instead
    '''
        
    def __init__(cls, name, bases, dict_):
        
        # Let GObjectMeta do it's initialization
        GObjectMeta.__init__(cls, name, bases, dict_)
        
        do_drag_data_get = dict_.get('do_drag_data_get')
        if do_drag_data_get:
            
            repo = GIRepository.Repository.get_default()
            
            for base in cls.__mro__:
                typeinfo = repo.find_by_gtype(base.__gtype__)
                if typeinfo:
                    vfunc = GIRepository.object_info_find_vfunc_using_interfaces(typeinfo, 'drag_data_get')
                    if vfunc:
                        break
            else:
                raise AttributeError("Could not find vfunc for drag_data_get")
            
            # Get the address of the vfunc so we can put our own callback in there
            address = vfunc_info_get_address(vfunc[0], cls.__gtype__)
            if address == 0:
                raise AttributeError("Could not get address for drag_data_get")
            
            # Make a thunk function closure, store it so it doesn't go out of scope
            do_drag_data_get._thunk = create_drag_data_get_thunk(cls)
            
            # Don't judge me... couldn't get a normal function pointer to work
            dbl_pointer = ctypes.POINTER(ctypes.c_void_p)
            addr = ctypes.cast(address, dbl_pointer)
            addr.contents.value = ctypes.cast(do_drag_data_get._thunk, ctypes.c_void_p).value


################################################################################
# The "with_metaclass()" method is included from the "six" library which has
# it's own copyright and license:
#
# Copyright (c) 2010-2017 Benjamin Peterson
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

def with_metaclass(meta, *bases):
    """Create a base class with a metaclass."""
    # This requires a bit of explanation: the basic idea is to make a dummy
    # metaclass for one level of class instantiation that replaces itself with
    # the actual metaclass.
    class metaclass(meta):

        def __new__(cls, name, this_bases, d):
            return meta(name, bases, d)
    return type.__new__(metaclass, 'temporary_class', (), {})

################################################################################

class PatchedListStore(with_metaclass(TreeDragSourceMeta, Gtk.ListStore)):
    '''ListStore object that can be used with the high-level TreeView DnD API'''
    pass

class PatchedTreeStore(with_metaclass(TreeDragSourceMeta, Gtk.TreeStore)):
    '''TreeStore object that can be used with the high-level TreeView DnD API'''
    pass
