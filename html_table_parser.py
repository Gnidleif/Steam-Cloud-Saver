#!/usr/bin/python3
from html.parser import HTMLParser
from typing_extensions import Self

class HTMLTableParser(HTMLParser):
    def __init__(self: Self, decode_html_entities: bool = True, data_separator: str = ' '):
        HTMLParser.__init__(self, convert_charrefs=decode_html_entities)
        self._data_separator = data_separator
        self._in_td = False
        self._in_th = False
        self._href = ''
        self._current_table = []
        self._current_row = []
        self._current_cell = []
        self.tables = []

    def handle_starttag(self, tag, attrs):
        for attr in attrs:
            if attr[0] == "href":
                self._href = attr[1]
                break

        if tag == "td":
            self._in_td = True
        elif tag == "th":
            self._in_th = True

    def handle_data(self, data):
        if self._in_td or self._in_th:
            if len(self._href) > 0:
                self._current_cell.append(self._href)
                self._href = ''
            else:
                self._current_cell.append(data.strip())
    
    def handle_endtag(self, tag):
        if tag == "td":
            self._in_td = False
        elif tag == "th":
            self._in_th = False

        if tag in ["td", "th"]:
            final_cell = self._data_separator.join(self._current_cell).strip()
            self._current_row.append(final_cell)
            self._current_cell = []
        elif tag == "tr":
            self._current_table.append(self._current_row)
            self._current_row = []
        elif tag == "table":
            self.tables.append(self._current_table)
            self._current_table = []