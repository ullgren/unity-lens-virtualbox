#! /usr/bin/python
#
# (C) Neil Jagdish Patel
#
# GPLv3
#

import sys
import os
from gi.repository import GLib, GObject, Gio
from gi.repository import Dee
# FIXME: Some weird bug in Dee or PyGI makes Dee fail unless we probe
#        it *before* we import the Unity module... ?!
# _m = dir(Dee.SequenceModel)
from gi.repository import Unity
from subprocess import call


#
# The primary bus name we grab *must* match what we specify in our .lens file
#
BUS_NAME = "net.launchpad.Unity.Lens.VBox"


class Daemon:

  def __init__(self):
    # The path for the Lens *must* also match the one in our .lens file
    self._lens = Unity.Lens.new("/net/launchpad/unity/lens/vbox", "vbox")
    self._lens.props.search_hint = "Search VirtualBox VMs"
    self._lens.props.visible = True
    self._lens.props.search_in_global = True

    self.populate_categories()
    self.populate_filters()

    # The Lens infrastructure is capable of having a Lens daemon run independantly
    # of it's Scopes, so you can have the Music Lens that does nothing but
    # add some filters and categories, but then, depending on which music player
    # the user uses, they can install the right scope and it'll all work.
    #
    # However, many times you want to ship something useful with your Lens, which
    # means you'll want to ship a scope to make things work. Instead of having to
    # create a separate daemon and jump through a bunch of hoops to make all that
    # work, you can create a Scope(s) in the same process and use the
    # lens.add_local_scope() method to let the Lens know that it exists.
    self._scope = UserScope()
    self._lens.add_local_scope(self._scope.get_scope())

    # Now we've set the categories and filters, export the Scope.
    self._lens.export()

  def populate_filters(self):
    filters = []

    # Radiooption is my favourite filter as it only allows the user to select on
    # option at a time, which does wonders for reducing the complexity of the code!
    # The first argument is the most important, it's an "id" that when a scope
    # queries the filter for the active option, it will receive back one of these
    # ids (i.e. the scope may receive "forms"). If it receives None, then that
    # means the user hasn't selected anything.
    f = Unity.RadioOptionFilter.new("type", "Type", Gio.ThemedIcon.new(""), False)
    f.add_option("running", "Running", None)
    f.add_option("all", "All", None)
    #f.add_option ("form", "Forms", None)
    #f.add_option ("presentation", "Presentations", None)
    #f.add_option ("drawing", "Drawings", None)
    #f.add_option ("pdf", "PDF Files", None)
    #f.add_option ("folder", "Folders", None)
    filters.append(f)

    #f = Unity.RadioOptionFilter.new ("ownership", "Ownership", Gio.ThemedIcon.new(""), False)
    #f.add_option ("mine", "Owned by me", None)
    #filters.append(f)

    self._lens.props.filters = filters

  def populate_categories(self):
    # Ideally we'd have more pertinant icons for our Lens, but for now we'll
    # steal Unitys :)
    icon_loc = "/usr/share/icons/unity-icon-theme/places/svg/group-recent.svg"
    cats = []

    # You should appent categories in the order you'd like them displayed
    # When you append a result to the model, the third integer argument is
    # actually telling Unity which Category you'd like the result displayed in.
    #
    # For example: To add something to "Modified Today", you would send '0' when
    # adding that result. For "Modified Earilier This Month", you would send '3'.
    #
    # The third, CategoryRenderer, argument allows you to hint to Unity how you
    # would like the results for that Category to be displayed.
    cats.append(Unity.Category.new("Running",
                                     Gio.ThemedIcon.new(icon_loc),
                                     Unity.CategoryRenderer.VERTICAL_TILE))
    cats.append(Unity.Category.new("Recently used",
                                     Gio.ThemedIcon.new(icon_loc),
                                     Unity.CategoryRenderer.VERTICAL_TILE))
    cats.append(Unity.Category.new("All",
                                     Gio.ThemedIcon.new(icon_loc),
                                     Unity.CategoryRenderer.VERTICAL_TILE))
    #cats.append (Unity.Category.new ("Modified Earlier This Month",
    #                                 Gio.ThemedIcon.new(icon_loc),
    #                                 Unity.CategoryRenderer.VERTICAL_TILE))
    #cats.append (Unity.Category.new ("Modified Earlier This Year",
    #                                 Gio.ThemedIcon.new(icon_loc),
    #                                 Unity.CategoryRenderer.VERTICAL_TILE))
    #cats.append (Unity.Category.new ("Modified Long Ago",
    #                                 Gio.ThemedIcon.new(icon_loc),
    #                                 Unity.CategoryRenderer.VERTICAL_TILE))
    self._lens.props.categories = cats


# Encapsulates searching a single user's GDocs
class UserScope:
  def __init__(self):
    # self._client = gdata.docs.client.DocsClient(source='njpatel-UnityLensGDocs-0.1')
    # self._client.ssl = True
    # self._client.http_client.debug = False

    # We don't have a good way to ask for the username/password yet and I don't
    # want everyone knowing my details so envvar it is :)
    # self._client.ClientLogin("GDOC_USERNAME",
    #                   "GDOC_PASSWORD",
    #                   self._client.source);

    self._scope = Unity.Scope.new("/net/launchpad/unity/scope/vbox")

    # Listen for changes and requests
    self._scope.connect("notify::active-search", self._on_search_changed)
    self._scope.connect("notify::active-global-search", self._on_global_search_changed)
    self._scope.connect("activate_uri", self._on_uri_activated)

    # This allows us to re-do the search if any parameter on a filter has changed
    # Though it's possible to connect to a more-specific changed signal on each
    # Fitler, as we re-do the search anyway, this catch-all signal is perfect for
    # us.
    self._scope.connect("filters-changed", self._on_search_changed)
    self._scope.export()

  def get_scope(self):
    return self._scope

  def get_search_string(self):
    search = self._scope.props.active_search
    return search.props.search_string if search else None

  def get_global_search_string(self):
    search = self._scope.props.active_global_search
    return search.props.search_string if search else None

  def search_finished(self):
    search = self._scope.props.active_search
    if search:
      search.emit("finished")

  def global_search_finished(self):
    search = self._scope.props.active_global_search
    if search:
      search.emit("finished")

  def _on_search_changed(self, scope, param_spec=None):
    search = self.get_search_string()
    results = scope.props.results_model

    print "Search changed to: '%s'" % search

    self._update_results_model(search, results)
    self.search_finished()

  def _on_global_search_changed(self, scope, param_spec):
    search = self.get_global_search_string()
    results = scope.props.global_results_model

    print "Global search changed to: '%s'" % search

    self._update_results_model(search, results, True)

    self.global_search_finished()

  def _update_results_model(self, search, model, is_global=False):
    # Clear out the current results in the model as we'll get a new list
    # NOTE: We could be clever and only remove/add things entries that have
    # changed, however the cost of doing that for a small result set probably
    # outweighs the gains. Especially if you consider the complexity,
    model.clear()

    # Get the list of documents
    vboxlist = self.get_vbox_list(search, is_global)
    for entry in vboxlist:
        model.append("VBoxManage startvm %s" % entry['uuid'],
                    "virtualbox",
                    0,
                    "application-x-desktop",
                    entry['title'].encode("UTF-8"),
                    "Start VM",
                    "application://VBoxManage%20startvm%20FreeDos")

  # This is where we do the actual search for documents
  def get_vbox_list(self, search, is_global):
    # stdout_handle = Popen("VBoxManage list vms", shell=True, bufsize=1024, stdout=subprocess.PIPE).stdout
    stdout_handle = os.popen("VBoxManage list vms", "r")
    result = []
    for line in  stdout_handle.readlines():
        [title, uuid] = line.rsplit(' ', 1)
        if not search or title.find(search.strip()) != -1:
          result.append({'title': title, 'uuid': uuid})
    return result

  def apply_filters(self, uri):
    # Try and grab a known filter and check whether or not it has an active
    # option. We've been clever and updated our filter option id's to match
    # what google expect in the request, so we can just use the id's when
    # constructing the uri :)
    f = self._scope.get_filter("type")
    if f != None:
      o = f.get_active_option()
      if o != None:
        uri += "/-/" + o.props.id

    f = self._scope.get_filter("ownership")
    if f != None:
      o = f.get_active_option()
      if o != None:
        uri += "/mine"

    return uri

  # Send back a useful icon depending on the document type
  def icon_for_type(self, doc_type):
    ret = "text-x-preview"

    if doc_type == "pdf":
      ret = "gnome-mime-application-pdf"
    elif doc_type == "drawing":
      ret = "x-office-drawing"
    elif doc_type == "document":
      ret = "x-office-document"
    elif doc_type == "presentation":
      ret = "libreoffice-oasis-presentation"
    elif doc_type == "spreadsheet" or doc_type == "text/xml":
      ret = "x-office-spreadsheet"
    elif doc_type == "folder":
      ret = "folder"
    else:
      print "Unhandled icon type: ", doc_type

    return ret

  def _on_uri_activated(self, scope, uri):
      print "on_uri_activated ", uri
      call(uri, shell=True)
      return Unity.ActivationResponse.new(Unity.HandledType.HIDE_DASH, "/")

if __name__ == "__main__":
  # NOTE: If we used the normal 'dbus' module for Python we'll get
  #       slightly odd results because it uses a default connection
  #       to the session bus that is different from the default connection
  #       GDBus (hence libunity) will use. Meaning that the daemon name
  #       will be owned by a connection different from the one all our
  #       Dee + Unity magic is working on...
  #       Still waiting for nice GDBus bindings to land:
  #                        http://www.piware.de/2011/01/na-zdravi-pygi/
  session_bus_connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
  session_bus = Gio.DBusProxy.new_sync(session_bus_connection, 0, None,
                                        'org.freedesktop.DBus',
                                        '/org/freedesktop/DBus',
                                        'org.freedesktop.DBus', None)
  result = session_bus.call_sync('RequestName',
                                 GLib.Variant("(su)", (BUS_NAME, 0x4)),
                                 0, -1, None)

  # Unpack variant response with signature "(u)". 1 means we got it.
  result = result.unpack()[0]

  if result != 1:
    print >> sys.stderr, "Failed to own name %s. Bailing out." % BUS_NAME
    raise SystemExit(1)

  daemon = Daemon()
  GObject.MainLoop().run()
