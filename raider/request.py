# Copyright (C) 2022 DigeeX
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


"""Request class used to handle HTTP.
"""

import logging
import sys
import urllib
from copy import deepcopy
from typing import Any, Dict, List, Optional, Union
from functools import partial

import requests
from urllib3.exceptions import InsecureRequestWarning

from raider.plugins.basic.cookie import Cookie
from raider.plugins.basic.file import File
from raider.plugins.basic.header import Header
from raider.plugins.common import Plugin
from raider.structures import CookieStore, DataStore, HeaderStore
from raider.user import User
from raider.utils import colors


def prompt_empty_value(element: str, name: str):
    value = input(
        colors["GREEN-BLACK-B"]
        + element
        + ' "'
        + colors["RED-BLACK-B"]
        + name
        + colors["GREEN-BLACK-B"]
        + '" has an empty value. '
        + "Input its value manually (enter to skip)\n"
        + colors["YELLOW-BLACK-B"]
        + name
        + " = "
    )
    return value


def process_cookies(
    raw_cookies: CookieStore, userdata: Dict[str, str]
) -> Dict[str, str]:
    """Process the raw cookies and replace with the real data."""
    cookies = raw_cookies.to_dict().copy()
    for key in raw_cookies:
        name = raw_cookies[key].name
        if raw_cookies[key].name_not_known_in_advance:
            cookies.pop(key)
        value = raw_cookies[key].get_value(userdata)
        if not value:
            value = prompt_empty_value("Cookie", name)
        if not value:
            cookies.pop(key)
        else:
            cookies.update({name: value})
    return cookies


def process_headers(
    raw_headers: HeaderStore, userdata: Dict[str, str], pconfig
) -> Dict[str, str]:
    """Process the raw headers and replace with the real data."""
    headers = raw_headers.to_dict().copy()
    headers.update({"user-agent": pconfig.user_agent})
    for key in raw_headers:
        name = raw_headers[key].name
        if raw_headers[key].name_not_known_in_advance:
            headers.pop(key)
        value = raw_headers[key].get_value(userdata)
        if not value:
            value = prompt_empty_value("Header", name)
        if not value:
            headers.pop(name.lower())
        else:
            headers.update({name: value})
    return headers


def process_data(
    raw_data: Dict[str, DataStore], userdata: Dict[str, str]
) -> Dict[str, str]:
    """Process the raw HTTP data and replace with the real data."""

    def traverse_dict(data: Dict[str, Any], userdata: Dict[str, str]) -> None:
        """Traverse a dictionary recursively and replace plugins
        with real data
        """
        for key in list(data):
            value = data[key]
            if isinstance(value, Plugin):
                new_value = value.get_value(userdata)
                if not new_value:
                    new_value = prompt_empty_value("Value", value.name)
                if not new_value:
                    data.pop(key)
                else:
                    data.update({key: new_value})
            elif isinstance(value, dict):
                traverse_dict(value, userdata)

            if isinstance(key, Plugin):
                new_value = data.pop(key)
                new_key = key.get_value(userdata)
                if not new_key:
                    new_key = prompt_empty_value("Key", key.name)
                if not new_key:
                    data.pop(key)
                else:
                    data.update({new_key: new_value})

    httpdata = {}
    for key, value in raw_data.items():
        new_dict = value.to_dict().copy()
        traverse_dict(new_dict, userdata)
        httpdata[key] = new_dict

    return httpdata


class Request:
    """Class holding the elements of the HTTP request.

    When a Flow object is created, it defines a Request object with
    the information necessary to create a HTTP request. The "method"
    and "url" attributes are required. Everything else is optional.

    The Request object can contain Plugins which will be evaluated and
    its value replaced in the HTTP request.

    Attributes:
      method:
        A string with the HTTP request method. Only GET and POST is
        supported for now.
      url:
        A string with the URL of the HTTP request.
      cookies:
        A list of Cookie objects to be sent with the HTTP request.
      headers:
        A list of Header objects to be sent with the HTTP request.
      data:
        A dictionary of Any objects. Can contain strings and
        Plugins. When a key or a value of the dictionary is a Plugin, it
        will be evaluated and its value will be used in the HTTP
        request. If the "method" is GET those values will be put inside
        the URL parameters, and if the "method" is POST they will be
        inside the POST request body.

    """

    def __init__(
        self,
        function,
        url: str,
        method: str,
        **kwargs
    ) -> None:
        """Initializes the Request object.
        """
        self.method = method
        self.function = function
        self.url = url

        self.logger = None
        self.headers = HeaderStore(kwargs.get("headers"))
        self.cookies = CookieStore(kwargs.get("cookies"))
        self.kwargs = kwargs

        data = {}
        for item, value in kwargs.items():
            if item in ["params", "data", "json", "multipart"]:
                data[item] = DataStore(value)
        self.data = data

    @classmethod
    def get(cls, url, **kwargs) -> "Request":
        return cls(function=requests.get,
                   url=url,
                   method="GET",
                   **kwargs)


    @classmethod
    def post(cls, url, **kwargs) -> "Request":
        return cls(function=requests.post,
                   url=url,
                   method="GET",
                   **kwargs)

    @classmethod
    def put(cls, url, **kwargs) -> "Request":
        return cls(function=requests.put,
                   url=url,
                   method="PUT",
                   **kwargs)


    @classmethod
    def patch(cls, url, **kwargs) -> "Request":
        return cls(function=requests.patch,
                   url=url,
                   method="PATCH",
                   **kwargs)


    @classmethod
    def head(cls, url, **kwargs) -> "Request":
        return cls(function=requests.head,
                   url=url,
                   method="HEAD",
                   **kwargs)


    @classmethod
    def delete(cls, url, **kwargs) -> "Request":
        return cls(function=requests.delete,
                   url=url,
                   method="DELETE",
                   **kwargs)

    @classmethod
    def connect(cls, url, **kwargs) -> "Request":
        function = partial(requests.request,
                           method="CONNECT")
        return cls(function=function,
                   url=url,
                   method="CONNECT",
                   **kwargs)

    @classmethod
    def options(cls, url, **kwargs) -> "Request":
        return cls(function=requests.options,
                   url=url,
                   method="OPTIONS",
                   **kwargs)

    @classmethod
    def trace(cls, url, **kwargs) -> "Request":
        function = partial(requests.request,
                           method="TRACE")
        return cls(function=function,
                   url=url,
                   method="TRACE",
                   **kwargs)

    @classmethod
    def custom(cls, method, url, **kwargs) -> "Request":
        function = partial(requests.request,
                           method=method)
        return cls(function=function,
                   url=url,
                   method=method,
                   **kwargs)
    



    def list_inputs(self) -> Optional[Dict[str, Plugin]]:
        """Returns a list of request's inputs."""

        def get_children_plugins(plugin: Plugin) -> Dict[str, Plugin]:
            """Returns the children plugins.

            If a plugin has the flag DEPENDS_ON_OTHER_PLUGINS set,
            return a dictionary with each plugin associated to its name.

            """
            output = {}
            if plugin.depends_on_other_plugins:
                for item in plugin.plugins:
                    output.update({item.name: item})
            return output

        inputs = {}

        if isinstance(self.url, Plugin):
            inputs.update({self.url.name: self.url})
            inputs.update(get_children_plugins(self.url))

        for name in self.cookies:
            cookie = self.cookies[name]
            inputs.update({name: cookie})
            inputs.update(get_children_plugins(cookie))

        for name in self.headers:
            header = self.headers[name]
            inputs.update({name: header})
            inputs.update(get_children_plugins(header))

        for key, value in self.data.items():
            if isinstance(key, Plugin):
                inputs.update({key.name: key})
                inputs.update(get_children_plugins(key))
            if isinstance(value, Plugin):
                inputs.update({value.name: value})
                inputs.update(get_children_plugins(value))

        return inputs

    def send(self, pconfig) -> Optional[requests.models.Response]:
        """Sends the HTTP request.

        With the given user information, replaces the input plugins with
        their values, and sends the HTTP request. Returns the response.

        Args:
          user:
            A User object with the user specific data to be used when
            processing inputs.
          pconfig:
            A Config object with the global Raider configuration.

        Returns:
          A requests.models.Response object with the HTTP response
          received after sending the generated request.

        """
        verify = pconfig.verify
        userdata = pconfig.active_user.to_dict() or {}

        self.logger = pconfig.logger
        if not verify:
            # False positive
            # pylint: disable=no-member
            requests.packages.urllib3.disable_warnings(
                category=InsecureRequestWarning
            )

        if pconfig.use_proxy:
            proxies = {"all": pconfig.proxy}
        else:
            proxies = None

        if isinstance(self.url, Plugin):
            self.url = self.url.get_value(userdata)

        cookies = process_cookies(self.cookies, userdata)
        headers = process_headers(self.headers, userdata, pconfig)
        processed = process_data(self.data, userdata)

        # Encode special characters. This will replace "+" signs with "%20"
        if "params" in self.kwargs:
            params = urllib.parse.urlencode(
                processed["params"], quote_via=urllib.parse.quote
            )
        else:
            params = None

        attrs = {"data", "json", "multipart"}.intersection(set(self.kwargs))
        if (self.method == "GET") and attrs:
            self.logger.warning("GET requests can only contain :params. Ignoring :" + ", :".join(attrs))
        elif attrs:
            self.logger.warning(self.method
                                + " requests cannot contain :"
                                + ", :".join(attrs)
                                + " at the same time. Undefined behaviour!")

        self.logger.debug("Sending HTTP request:")
        self.logger.debug("%s %s", self.method, self.url)
        self.logger.debug("Cookies: %s", str(cookies))
        self.logger.debug("Headers: %s", str(headers))
        self.logger.debug("Params: %s", str(params))
        self.logger.debug("Data: %s", str(processed.get("data")))
        self.logger.debug("JSON: %s", str(processed.get("json")))
        self.logger.debug("Multipart: %s", str(processed.get("multipart")))

        try:
            req = self.function(
                url=self.url,
                headers=headers,
                cookies=cookies,
                proxies=proxies,
                verify=verify,
                allow_redirects=False,
                params=params,
                data=processed.get("data"),
                json=processed.get("json"),
                files=processed.get("multipart")
            )
        except requests.exceptions.ProxyError:
            self.logger.critical("Cannot establish connection!")
            sys.exit()

        return req

class Template(Request):
    """Template class to hold requests.

    It will initiate itself with a :class:`Request
    <raider.request.Request>` parent, and when called will return a
    copy of itself with the modified parameters.

    """

    def __init__(
        self,
        method: str,
        url: Optional[Union[str, Plugin]] = None,
        cookies: Optional[List[Cookie]] = None,
        headers: Optional[List[Header]] = None,
        data: Optional[Union[Dict[Any, Any]]] = None,
    ) -> None:
        """Initializes the template object."""
        function = partial(requests.request,
                           method=method)
        super().__init__(
            function=function,
            method=method,
            url=url,
            cookies=cookies,
            headers=headers,
            data=data,
        )

    def __call__(
        self,
        method: Optional[str] = None,
        url: Optional[Union[str, Plugin]] = None,
        cookies: Optional[List[Cookie]] = None,
        headers: Optional[List[Header]] = None,
        data: Optional[Union[Dict[Any, Any]]] = None,
    ) -> "Template":
        """Allow the object to be called.

        Accepts the same arguments as the :class:`Request
        <raider.request.Request>` class. When called, will return a copy
        of itself with the modified parameters.

        """
        template = deepcopy(self)

        if method:
            template.method = method

        if url:
            template.url = url

        if cookies:
            template.cookies.merge(CookieStore(cookies))

        if headers:
            template.headers.merge(HeaderStore(headers))

        if data:
            template.data.update(data)

        return template
