"""Middleware to communicate with PubSub Message Broker."""
from collections.abc import Callable
from enum import Enum
from queue import LifoQueue, Empty
from typing import Any

import socket, json, pickle, selectors
import xml.etree.ElementTree as ET

class MiddlewareType(Enum):
    """Middleware Type."""

    CONSUMER = 1
    PRODUCER = 2


class Queue:
    """Representation of Queue interface for both Consumers and Producers."""

    def __init__(self, topic, _type=MiddlewareType.CONSUMER):
        """Create Queue."""
        self.topic = topic
        self._type = _type
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(('localhost', 5000))
        self.sele=selectors.DefaultSelector()
        self.sele.register(self.sock, selectors.EVENT_READ, self.pull)
    
    def send_msg(self,method,topic, value):
        """Send data to broker."""
        msg=self.encode(method, topic, value)
        self.sock.send(len(msg).to_bytes(2, 'big') + msg)

    def push(self, value):
        """Sends data to broker."""
        self.send_msg("PUBLISH",self.topic, value)
        

    def pull(self) -> (str, Any):
        """Receives (topic, data) from broker.
        Should BLOCK the consumer!"""
        header=self.sock.recv(2)
        if not header:
            return None
        length=int.from_bytes(header, 'big')
        data=self.sock.recv(length)

        if data:       
            topic, value = self.decode(data)
            return topic, value
        else:
            return None,None


    def list_topics(self, callback: Callable):
        """Lists all topics available in the broker."""
        self.send_msg("LIST_TOPICS",self.topic, "")
        
    def cancel(self):
        """Cancel subscription."""
        self.send_msg("CANCEL",self.topic, "")
        

        


class JSONQueue(Queue):
    """Queue implementation with JSON based serialization."""
    def __init__(self, topic, _type=MiddlewareType.CONSUMER):
        super().__init__(topic, _type)
        msg = json.dumps({"method" : "serialize", "value" : "JSON"}).encode("utf-8")
        self.sock.send(len(msg).to_bytes(2, 'big') + msg)

        if self._type == MiddlewareType.CONSUMER:
            msg=self.encode("SUBSCRIBE", self.topic, "")
            self.sock.send(len(msg).to_bytes(2, 'big') + msg)

    def encode(self, method, topic, value):
        """Encode data to JSON."""
        msg=json.dumps({"method": method, "topic": topic, "value": value}).encode("utf-8")
        return msg

    def decode(self, data):
        """Decode data from JSON."""
        msg=json.loads(data.decode("utf-8"))
        method=msg["method"]
        if not "topic" in msg:
            topic=None
        else:
            topic=msg["topic"]
        if not "value" in msg:
            value=None
        else:
            value=msg["value"]
        return topic, value

class XMLQueue(Queue):
    """Queue implementation with XML based serialization."""
    def __init__(self, topic, _type=MiddlewareType.CONSUMER):
        super().__init__(topic, _type)
        msg = {"method": "serialize", "value": "XML"}
        msg = ('<?xml version="1.0"?><data method="%(method)s"><value>%(value)s</value></data>' % msg)
        msg = msg.encode('utf-8')
        self.sock.send(len(msg).to_bytes(2, 'big') + msg)

        if self._type == MiddlewareType.CONSUMER:
            msg=self.encode("SUBSCRIBE", self.topic, "")
            self.sock.send(len(msg).to_bytes(2, 'big') + msg)

    def encode(self, method, topic, value):
        """Encode data to XML."""
        msg = {"method": method, "topic": topic, "value": value}
        msg = ('<?xml version="1.0"?><data method="%(method)s" topic="%(topic)s"><value>%(value)s</value></data>' % msg)
        msg = msg.encode('utf-8')
        return msg
    
    def decode(self, data):
        """Decode data from XML."""
        root = ET.fromstring(data.decode("utf-8"))
        msg = {}
        
        for el in tree.iter():
            msg[el.tag] = el.text
        
        method = msg["method"]
        if not "topic" in msg:
            topic=None
        else:
            topic=msg["topic"]
        if not "value" in msg:
            value=None
        else:
            value=root.find('value').text
        return topic, value


class PickleQueue(Queue):
    """Queue implementation with Pickle based serialization."""
    def __init__(self, topic, _type=MiddlewareType.CONSUMER):
        super().__init__(topic, _type)
        msg = pickle.dumps({"method" : "serialize", "value" : "PICKLE"})
        self.sock.send(len(msg).to_bytes(2, 'big') + msg)

        if self._type == MiddlewareType.CONSUMER:
            msg=self.encode("SUBSCRIBE", self.topic, "")
            self.sock.send(len(msg).to_bytes(2, 'big') + msg)


    def encode(self, method, topic, value):
        """Encode data to Pickle."""
        msg= pickle.dumps({"method": method, "topic": topic, "value": value})
        return msg

    def decode(self, data):
        """Decode data from Pickle."""
        msg=pickle.loads(data)
        method=msg["method"]
        if not "topic" in msg:
            topic=None
        else:
            topic=msg["topic"]
        if not "value" in msg:
            value=None
        else:
            value=msg["value"]
        return  topic, value
