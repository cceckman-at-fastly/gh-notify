#!/usr/bin/env python3


try:
    import dbus
except Error:
    print("Install dbus-python from your favorite package repository")

"""
Watch Github's notifications REST endpoint, and pop up desktop notifications when there are new ones.
"""

from urllib import request
from urllib.error import HTTPError
import json
import subprocess
import time

def get_token() -> str:
    """
    Get a personal authentication token.
    """
    result = subprocess.run(["gh", "auth", "token"], capture_output=True)
    result.check_returncode()
    result = result.stdout.decode("utf-8").strip()
    return result

def send_notification(reason, repository):
    # From https://pychao.com/2021/03/01/sending-desktop-notification-in-linux-with-python-with-d-bus-directly/
    item = "org.freedesktop.Notifications"

    notfy_intf = dbus.Interface(
        dbus.SessionBus().get_object(item, "/"+item.replace(".", "/")), item)

    # https://specifications.freedesktop.org/notification-spec/1.2/protocol.html#command-notify
    notfy_intf.Notify(
        "GitHub", # app_name
        0, # replaces_id
        "", # app_icon
        f"{reason} in {repository}", # summary / title
        "", # body
        [], # actions; TODO: put a link here
        [], # hints
        0, # expire_timeout; 0 for no expiry
    )
    print(f"{reason} in {repository}")

def single_cycle(last_modified: None, ids: set) -> (int, str):
    """
    Run a single cycle of polling for updates.
    Returns: (seconds to wait before next poll, last-modified header)
    """
    token = get_token()

    headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
    }
    if last_modified is not None:
        headers["If-Modified-Since"] = last_modified

    req = request.Request(
            "https://api.github.com/notifications",
        headers=headers,
    )
    try:
        with request.urlopen(req) as resp:
            poll_interval = resp.headers["X-Poll-Interval"]
            last_modified = resp.headers["Last-Modified"]
            body = bytes()
            while chunk := resp.read(4096):
                body += chunk

        body = body.decode("utf-8")
        data = json.loads(body)
        for notification in data:
            try:
                reason = notification["reason"]
                identity = notification["id"]
                name = notification["repository"]["full_name"]
            except Exception as e:
                print(f"failed to interpret notification from body: \n{body}\n")
                raise e

            ids.add(identity)
            send_notification(reason, name)

        return (int(poll_interval), last_modified)

    except HTTPError as e:
        poll_interval = e.headers["X-Poll-Interval"]
        last_modified = e.headers["Last-Modified"]

        if e.code == 304:
            return (poll_interval, last_modified)
        else:
            print(f"got response: {e}")
            return (None, None)
        raise e

def repeat():
    last_modified = None
    ids = set()
    while True:
        print("running poll")
        (poll, lm) = single_cycle(last_modified, ids)
        last_modified = lm

        if poll is None:
            poll = 60

        p = int(poll)
        print(f"sleeping for {p} seconds")
        time.sleep(p)

if __name__ == "__main__":
    repeat()

