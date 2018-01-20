"""
Inspector page, used for viewing objects in the database.
"""
from .pylib import server


class Tab:
    """
    Base class of tabs, including the menu link and the displayed tab itself.
    """
    Name = ""
    """Friendly name to be displayed in the menu."""
    Data_tab = ""
    """Tab identifier, used as html attribute 'data-tab'."""
    Active = False
    """True if this Tab should be displayed on startup."""

    def __init__(self):
        self._menu_attrs = {"data-tab": self.Data_tab}
        self._tab_attrs = {"data-tab": self.Data_tab}
        self._menu = "a.item"
        self._tab = "div.ui.bottom.attached.tab.segment.no-border.below-tabs"

        if self.Active:
            self._menu += ".active"
            self._tab += ".active"

    def menu_item(self):
        """
        Returns a vnode <a> item, for use in the tab menu.
        """
        return m(self._menu, self._menu_attrs, self.Name)

    def tab_item(self):
        """
        Returns a vnode tab wrapper around the contents of the tab itself.
        """
        return m(self._tab, self._tab_attrs, self.main_view())

    def main_view(self):
        """
        Returns the vnode of the actual tab contents.
        """
        return m("div", "hello " + self.Name)


class TabledTab(Tab):
    """
    Base class for tabs in the Inspector interface, using a table and "details" view.
    """
    def __init__(self):
        super().__init__()
        self.table = None
        self.setup_table()
        self.copiedDetails = ""
        self._detailsId = self.Data_tab + "DetailsCodeBlock"
        self._copiedId = self.Data_tab + "CopiedCodeBlock"
        self._copyButtonId = self.Data_tab + "CopyButton"
        self._clearButtonId = self.Data_tab + "ClearButton"

    def setup_table(self):
        """
        Called on startup for the purpose of creating the Table object.
        """
        self.table = Table([])

    def _copyDetails(self):
        self.copiedDetails = self.table.detailSelected

    def _getRows(self):
        return jQuery("[data-tab='{0}'].tab table > tbody > tr".format(self.Data_tab))

    def _getLabel(self):
        return jQuery(".menu a[data-tab='{0}'] .ui.label".format(self.Data_tab))

    def _clearCopy(self):
        self.copiedDetails = ""

    def menu_item(self):
        return m(self._menu, self._menu_attrs,
                 m("div", self.Name),
                 m("div.ui.label.small", "{0}/{1}".format(self.table.shown, self.table.total))
                 )

    def main_view(self):
        return m("div.fill-container.small-padding",
                 # Table needs to be in a special container to handle scrolling/sticky table header
                 m("div.table-container", m(self.table.view)),
                 m("div.card-container",
                   m("div.ui.two.cards.fill-container",
                     m("div.ui.card",
                       m("div.content.small-header",
                         m("div.header",
                           m("span", "Details"),
                           m("span.ui.mini.right.floated.button", {"onclick": self._copyDetails, "id": self._copyButtonId},
                             "Copy")
                           )
                         ),
                       m("pre.content.code-block", {"id": self._detailsId},
                         self.table.detailSelected
                         )
                       ),
                     m("div.ui.card",
                       m("div.content.small-header",
                         m("div.header",
                           m("span", "Copied"),
                           m("span.ui.mini.right.floated.button", {"onclick": self._clearCopy, "id": self._clearButtonId},
                             "Clear")
                           )
                         ),
                       m("pre.content.code-block", {"id": self._copiedId},
                         self.copiedDetails
                         )
                       )
                     )
                   )
                 )


class Field:
    """
    A field/column of a table.

    Attributes:
        title (str): Friendly table header name
        name (str): JSON key to use in data lookup by default
    """
    Title = None
    """Friendly name to display in table header."""
    Length = 4
    """Length of string to display before truncating with ellipses"""

    __pragma__("kwargs")
    def __init__(self, title=None, length=None):
        self.title = self.Title
        if title is not None:
            self.title = title

        # Cannot assign "length" to object
        self.mlength = self.Length
        if length is not None:
            self.mlength = length

        self.name = self.title.lower()
    __pragma__("nokwargs")

    def format(self, data):
        """
        Formats the data to a string matching the expected view for this field.
        """
        return str(data)

    def shorten(self, string):
        """
        Shortens the string to an appropriate length for display.
        """
        return string

    def view(self, data):
        """
        Returns a vnode <td> suitable for display in a table.
        """
        if data == None:
            # Better to have empty data than to cause an error
            data = ""
        formatted = self.format(data)
        return m("td", {"title": formatted}, self.shorten(formatted))


class FillField(Field):
    """
    Field that should "use remaining space" for display.
    """
    Length = 100

    def view(self, data):
        node = super().view(data)
        node.attrs["class"] = "fill-space"
        return node

class DateField(Field):
    """
    Field for displaying dates.
    """
    Length = 12
    Title = "Date"

class EpochField(DateField):
    """
    Field for displaying time since the epoch.
    """
    def format(self, data):
        # Make format match that of other typical dates from server
        data = __new__(Date(data / 1000)).toISOString()
        return super().format(data)


class IDField(Field):
    """
    Field for displaying ids.
    """
    Length = 4
    Title = "UID"
    Header = ""
    """Stripped from beginning of string for displaying."""

    def format(self, string):
        if string.startswith(self.Header):
            string = string[len(self.Header):]
        return super().format(string)

class DIDField(IDField):
    Header = "did:igo:"
    Title = "DID"

class HIDField(IDField):
    Header = "hid:"
    Title = "HID"

    # def shorten(self, string):
    #     if len(string) > 13:
    #         string = string[:6] + "..." + string[-4:]
    #     return string

class OIDField(IDField):
    Header = "o_"
    Title = "UID"

class MIDField(IDField):
    Header = "m_"
    Title = "UID"


class Table:
    """
    A table, its headers, and its data to be displayed.

    Attributes:
        max_size (int): maximum number of entries to display
        total (int): number of entries in our data
        shown (int): number of entries not hidden by filter or max_size limit
    """
    no_results_text = "No results found."

    def __init__(self, fields):
        self.max_size = 1000
        self.fields = fields
        self.data = []
        self._shownData = []
        self.view = {
            # "oninit": self.refresh,
            "view": self._view
        }

        self._selected = None
        self.detailSelected = ""

        self.filter = None
        self.sortField = None
        self.reversed = False

        self.total = 0
        self.shown = 0

    def _stringify(self, obj):
        """
        Converts the provided json-like object to a user-friendly string.
        """
        def replacer(key, value):
            # Hide any keys starting with underscore
            if key.startswith("_"):
                return
            return value
        return JSON.stringify(obj, replacer, 2)

    def _limitText(self):
        return "Limited to {} results.".format(self.max_size)

    def _selectRow(self, event, obj):
        """
        Deselects any previously selected row and
        selects the row specified in the event.
        """
        if self._selected is not None:
            # Deselect the last-selected object
            del self._selected._selected

            if self._selected._uid == obj._uid:
                # Remove the current selection and don't set another
                self._selected = None
                self.detailSelected = ""
                return

        # Select the new object
        self._selected = obj
        obj._selected = True
        self.detailSelected = self._stringify(obj)

    def refresh(self):
        """
        Refreshes any data from the server and returns a promise which resolves
        when finished.
        """
        self._setData([])
        p = __new__(Promise(lambda resolve: resolve()))
        return Promise

    def clear(self):
        """
        Removes memory of all current data.
        """
        self.total = 0
        server.clearArray(self.data)

    def _makeDummyData(self, count):
        data = []
        for i in range(count):
            obj = {}
            for field in self.fields:
                obj[field.name] = "test{0} {1}".format(i, field.name)
            data.append(obj)
        return data

    __pragma__("kwargs")
    def _setData(self, data, clear=True):
        """
        Clears existing data and uses the provided data instead.
        Adds a "_uid" field to each piece of data, for tracking internally.
        """
        if clear:
            self.clear()
        for datum in data:
            datum._uid = self.total
            self.data.append(datum)
            self.total += 1
        self._processData()
    __pragma__("nokwargs")

    def setFilter(self, func):
        if func != self.filter:
            self.filter = func
            self._processData()

    def setSort(self, field):
        """
        Sets our sort to be on the given field.
        If this is the same as our currently-sorting field, then reverses the sort
        on that same field.
        """
        if self.sortField == field:
            self.reversed = not self.reversed
        else:
            self.reversed = False
            self.sortField = field

        self._sortData()

    def _sortData(self):
        if self.sortField is None:
            return

        self._shownData.sort(key=lambda obj: self._getField(obj, self.sortField), reverse=self.reversed)

    def _processData(self):
        """
        Processes our data, determining which items to show and putting them into
        a list that is sorted if necessary.
        """
        server.clearArray(self._shownData)

        self.shown = 0
        for obj in self.data:
            if self.shown >= self.max_size:
                break
            if self.filter is not None:
                if not self.filter(obj):
                    continue

            self._shownData.append(obj)
            self.shown += 1

        self._sortData()

    def _getField(self, obj, field):
        """
        Gets the info from the object matching the given field.
        """
        return obj[field.name]

    def _makeRow(self, obj):
        """
        Called on each item in self.data.
        Returns an array of <td> vnodes representing a row.
        """
        return [field.view(self._getField(obj, field)) for field in self.fields]

    def _view(self):
        # Create the headers
        headers = []
        for field in self.fields:
            def makeScope(f):
                return lambda event: self.setSort(f)
            if field == self.sortField:
                if self.reversed:
                    icon = m("i.arrow.down.icon")
                else:
                    icon = m("i.arrow.up.icon")
                header = m("th.ui.right.labeled.icon", {"onclick": makeScope(field)},
                           icon,
                           field.title)
            else:
                header = m("th", {"onclick": makeScope(field)}, field.title)

            headers.append(header)

        # Create the rows
        rows = []
        for obj in self._shownData:
            row = self._makeRow(obj)

            # Needed so we can pass through the object as-is to the lambda, without it changing through the loop
            def makeScope(o):
                return lambda event: self._selectRow(event, o)
            if obj._selected:
                rows.append(m("tr.active", {"onclick": makeScope(obj)}, row))
            else:
                rows.append(m("tr", {"onclick": makeScope(obj)}, row))

        if self.shown >= self.max_size:
            rows.append(m("tr", m("td", self._limitText())))

        if not self.shown:
            rows.append(m("tr", m("td", self.no_results_text)))

        return m("table", {"class": "ui selectable celled unstackable single line left aligned table"},
                 m("thead",
                   m("tr", {"class": "center aligned"}, headers)
                   ),
                 m("tbody",
                   rows
                   )
                 )


class AnonMsgsTable(Table):
    def __init__(self):
        fields = [
            IDField("UID"),
            DateField(),
            EpochField("Created"),
            EpochField("Expire"),
            FillField("Content")
        ]
        super().__init__(fields)

    def refresh(self):
        self.clear()
        msgs = server.manager.anonMsgs
        return msgs.refresh().then(lambda: self._setData(msgs.messages))

    def _getField(self, obj, field):
        if field.name == "uid":
            return obj.anon.uid
        elif field.name == "date":
            return obj.anon.date
        elif field.name == "content":
            return obj.anon.content
        elif field.name == "created":
            return obj.create
        return obj[field.name]


class IssuantsTable(Table):
    def __init__(self):
        fields = [
            DIDField(),
            Field("Kind"),
            FillField("Issuer"),
            DateField("Registered"),
            FillField("URL")
        ]
        super().__init__(fields)

    def refresh(self):
        self.clear()
        entities = server.manager.entities
        return entities.refreshIssuants().then(lambda: self._setData(entities.issuants))

    def _getField(self, obj, field):
        if field.name == "url":
            return obj.validationURL
        return obj[field.name]


class OffersTable(Table):
    def __init__(self):
        fields = [
            OIDField("UID"),
            DIDField("Thing"),
            DIDField("Aspirant"),
            Field("Duration", length=5),
            DateField("Expiration"),
            DIDField("Signer"),
            DIDField("Offerer")
        ]
        super().__init__(fields)

    def refresh(self):
        self.clear()
        entities = server.manager.entities
        return entities.refreshOffers().then(lambda: self._setData(entities.offers))


class MessagesTable(Table):
    def __init__(self):
        fields = [
            MIDField("UID"),
            Field("Kind", length=8),
            DateField(),
            DIDField("To"),
            DIDField("From"),
            DIDField("Thing"),
            Field("Subject", length=10),
            FillField("Content")
        ]
        super().__init__(fields)

    def refresh(self):
        self.clear()
        entities = server.manager.entities
        return entities.refreshMessages().then(lambda: self._setData(entities.messages))


class EntitiesTable(Table):
    def __init__(self):
        fields = [
            DIDField(),
            HIDField(),
            DIDField("Signer"),
            DateField("Changed"),
            Field("Issuants"),
            FillField("Data"),
            Field("Keys")
        ]
        super().__init__(fields)

    def refresh(self):
        self.clear()
        entities = server.manager.entities
        p1 = entities.refreshAgents().then(lambda: self._setData(entities.agents, clear=False))
        p2 = entities.refreshThings().then(lambda: self._setData(entities.things, clear=False))
        return Promise.all([p1, p2])

    def _getField(self, obj, field):
        if field.name == "issuants":
            issuants = obj[field.name]
            # If any issuants provided, just show count
            if issuants:
                return len(issuants)
            else:
                return ""
        elif field.name == "keys":
            keys = obj[field.name]
            # If an keys provided, just show count
            if keys:
                return len(keys)
            else:
                return ""
        elif field.name == "data":
            d = obj[field.name]
            if d and d.keywords and d.message:
                data = " ".join(d.keywords)
                return data + " " + d.message
            else:
                return ""
        return obj[field.name]


class Entities(TabledTab):
    Name = "Entities"
    Data_tab = "entities"
    Active = True

    def setup_table(self):
        self.table = EntitiesTable()


class Issuants(TabledTab):
    Name = "Issuants"
    Data_tab = "issuants"

    def setup_table(self):
        self.table = IssuantsTable()


class Offers(TabledTab):
    Name = "Offers"
    Data_tab = "offers"

    def setup_table(self):
        self.table = OffersTable()


class Messages(TabledTab):
    Name = "Messages"
    Data_tab = "messages"

    def setup_table(self):
        self.table = MessagesTable()


class AnonMsgs(TabledTab):
    Name = "Anon Msgs"
    Data_tab = "anonmsgs"

    def setup_table(self):
        self.table = AnonMsgsTable()


class Searcher:
    """
    Methods for searching for a certain string in any dict object.

    Attributes:
        searchTerm (str): current string to search for
        caseSensitive (bool): if True, searches are case sensitive
    """
    def __init__(self):
        self.searchTerm = None
        self.caseSensitive = False

    def setSearch(self, term):
        """
        Sets our search term.
        If term is surrounded by quotes, removes them and makes the search
        case sensitive. Otherwise, the search is not case sensitive.

        Args:
            term (str): base string to search for
        """
        self.searchTerm = term or ""
        self.caseSensitive = self.searchTerm.startswith('"') and self.searchTerm.endswith('"')
        if self.caseSensitive:
            # Remove surrounding quotes
            self.searchTerm = self.searchTerm[1:-1]
        else:
            self.searchTerm = self.searchTerm.lower()

    def _checkPrimitive(self, item):
        """
        Checks for .searchTerm in the provided string.
        """
        if isinstance(item, str):
            if not self.caseSensitive:
                item = item.lower()
            return self.searchTerm in item
        return False

    def _checkAny(self, value):
        """
        Checks for .searchTerm in any provided dict, list, or primitive type
        """
        if isinstance(value, dict) or isinstance(value, Object):
            return self.search(value)
        elif isinstance(value, list):
            for item in value:
                if self._checkAny(item):
                    return True
            return False
        else:
            return self._checkPrimitive(value)

    def search(self, obj: dict):
        """
        Returns True if obj recursively contains the .searchTerm string in any field.
        """
        __pragma__("jsiter")
        for key in obj:
            if key.startswith("_"):
                # Skip any "private" keys
                continue

            value = obj[key]
            if self._checkAny(value):
                return True
        return False
        __pragma__("nojsiter")


class Tabs:
    """
    Manages the displayed tabs.
    """
    def __init__(self):
        self.tabs = [Entities(), Issuants(), Offers(), Messages(), AnonMsgs()]
        self._searchId = "inspectorSearchId"
        self.searcher = Searcher()

        self._refreshing = False
        self._refreshPromise = None

        # Required to activate tab functionality (so clicking a menu item will activate that tab)
        jQuery(document).ready(lambda: jQuery('.menu > a.item').tab())

        self.refresh()

    def refresh(self):
        """
        Retrieves server data and populates our tabs and tables.
        """
        if self._refreshing:
            return self._refreshPromise
        self._refreshing = True

        promises = []
        for tab in self.tabs:
            promises.append(tab.table.refresh())

        def done():
            self._refreshing = False

        self._refreshPromise = Promise.all(promises)
        self._refreshPromise.then(done)
        self._refreshPromise.catch(done)
        return self._refreshPromise

    def currentTab(self):
        """
        Returns the current Tab, or None if not found.
        """
        active = jQuery(".menu a.item.active")
        data_tab = active.attr("data-tab")
        for tab in self.tabs:
            if tab.Data_tab == data_tab:
                return tab
        return None

    def searchAll(self):
        """
        Initiates searching across all tabs based on the current search string.
        """
        text = jQuery("#" + self._searchId).val()
        self.searcher.setSearch(text)

        for tab in self.tabs:
            tab.table.setFilter(self.searcher.search)
        return False # Don't reload page on form submission

    def searchCurrent(self):
        """
        Initiates searching in the current tab based on the current search string.
        Clears any searches in other tabs.
        """
        text = jQuery("#" + self._searchId).val()
        self.searcher.setSearch(text)

        current = self.currentTab()

        # Clear any previous tab's searches and apply current search to current tab
        for tab in self.tabs:
            if text and tab.Data_tab == current.Data_tab:
                tab.table.setFilter(self.searcher.search)
            else:
                tab.table.setFilter(None)

    # def searchWithin(self):
    #     text = jQuery("#" + self._searchId).val()

    def view(self):
        menu_items = []
        tab_items = []
        for tab in self.tabs:
            menu_items.append(tab.menu_item())
            tab_items.append(tab.tab_item())

        if self._refreshing:
            refresher = m("button.ui.icon.button.disabled", {"onclick": self.refresh},
                          m("i.refresh.icon.spinning")
                          )
        else:
            refresher = m("button.ui.icon.button", {"onclick": self.refresh},
                          m("i.refresh.icon")
                          )

        return m("div", {"style": "height: 100%;"},
                 m("form", {"onsubmit": self.searchAll},
                   m("div.ui.borderless.menu",
                     m("div.right.menu", {"style": "padding-right: 40%"},
                       m("div.item", {"style": "width: 80%"},
                         m("div.ui.transparent.icon.input",
                           m("input[type=text][placeholder=Search...]", {"id": self._searchId}),
                           m("i.search.icon")
                           )
                         ),
                       m("div.item",
                         m("input.ui.primary.button[type=submit][value=Search]")
                         ),
                       m("div.item",
                         refresher
                         )
                       # m("div.item",
                       #   m("div.ui.secondary.button", {"onclick": self.searchWithin}, "Search Within")
                       #   )
                       )
                     ),
                   ),
                 m("div.ui.top.attached.pointing.five.item.menu",
                   menu_items
                   ),
                 tab_items
                 )
