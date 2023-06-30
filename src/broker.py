"""Message Broker"""
import enum
from typing import Dict, List, Any, Tuple

import socket, json, pickle, selectors
import xml.etree.ElementTree as ET

class Serializer(enum.Enum):
    """Possible message serializers."""

    JSON = 0
    XML = 1
    PICKLE = 2


class Broker:
    """Implementation of a PubSub Message Broker."""

    def __init__(self):
        """Initialize broker."""
        self.canceled = False
        self._host = "localhost"
        self._port = 5000
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((self._host, self._port))
        self.sock.listen()
        self.sele=selectors.DefaultSelector()
        self.sele.register(self.sock, selectors.EVENT_READ, self.accept)
        self.topics = {}
        self.subscribers = {}
        self.sockets = {}
        

    def list_topics(self) -> List[str]:
        """Returns a list of strings containing all topics containing values."""
        return [topics for topics in self.topics ]

    def get_topic(self, topic):
        """Returns the currently stored value in topic."""
        for i in self.topics: 
            if topic.startswith(i): 
                if len(self.topics[topic]) > 0: 
                    return self.topics[topic][-1] 
        return None

    def put_topic(self, topic, value):
        """Store in topic the value."""
        if topic not in self.topics:
            self.topics[topic] = [value]
        else:
            self.topics[topic].append(value)

    def list_subscriptions(self, topic: str) -> List[Tuple[socket.socket, Serializer]]:
        """Provide list of subscribers to a given topic."""
        return [key for key,values in self.subscribers.items() if topic in values]
      

    def subscribe(self, topic: str, address: socket.socket, _format: Serializer = None):
        """Subscribe to topic by client in address."""
        if (address, _format) not in self.subscribers:
            self.subscribers[(address, _format)] = [topic]
        elif topic not in self.subscribers[(address, _format)]:
            self.subscribers[(address, _format)].append(topic)


    def unsubscribe(self, topic, address):
        """Unsubscribe to topic by client in address."""
        for key in self.subscribers:
            if address in key:
                if topic in self.subscribers[key]:
                    self.subscribers[key].remove(topic)

    def encode(self, method, topic, value, serialize):
        """Encode data to be sent."""
        if serialize == "JSON":
            if topic is None:
                msg= json.dumps({"method": method, "value": value}).encode("utf-8")
            else:
                msg= json.dumps({"method": method, "topic": topic, "value": value}).encode("utf-8")
            return msg

        elif serialize == "XML":
            msg = {"method": method, "topic": topic, "value": value}
            if topic is None:
                msg = ('<?xml version="1.0"?><data method="%(method)s"><value>%(value)s</value></data>' % msg)
            else:
                msg = ('<?xml version="1.0"?><data method="%(method)s" topic="%(topic)s"><value>%(value)s</value></data>' % msg)
            msg = msg.encode('utf-8')            
            return msg

        elif serialize == "PICKLE":
            if topic is None:
                msg= pickle.dumps({"method": method, "value": value})
            else:
                msg= pickle.dumps({"method": method, "topic": topic, "value": value})
            return msg

    def decode(self, data, serialize):
        """Decode data received."""
        if serialize == "JSON":
            
            return json.loads(data.decode('utf-8'))

        elif serialize == "XML":
            root = ET.fromstring(data.decode('utf-8'))
            msg={}
            for child in root:
                msg[child.tag]=child.text

            return msg

        elif serialize == "PICKLE":
            return pickle.loads(data)


    def accept(self, sock, mask):
        conn, addr = self.sock.accept()
        print("accepted", conn, "from", addr)
        self.sele.register(conn, selectors.EVENT_READ, self.read)

    def read(self, conn, mask):

            header = conn.recv(2)
            header = int.from_bytes(header, 'big')
            length = conn.recv(header)

            if  len(length) != 0:
                if conn in self.sockets:
                    serialize = self.sockets[conn]
                else:
                    serialize = "JSON"
                data = self.decode(length, serialize)
            else:
                data = None


            if data != None:  #falta completar geral            
                if (conn not in self.sockets):
                    self.sockets[conn] = data["value"]

                method = data["method"]
                if not "value" in data:
                    value = None
                else:
                    value = data["value"]
                if not "topic" in data:
                    topic = None
                else:
                    topic = data["topic"]


                if method == "PUBLISH":
                    self.put_topic(topic, value)
                    for key,values in self.subscribers.items():
                        connect=key[0]
                        for i in values:
                            if topic.startswith(i):
                                msg=self.encode("PUBLISH_REP",  topic,  value, serialize)
                                conn.send(len(msg).to_bytes(2, 'big')+msg)

                elif method == "SUBSCRIBE":
                    self.subscribe(topic, conn)
                    final_topic= self.get_topic(topic)

                    if final_topic != None and topic != None:
                        msg=self.encode("SUBSCRIBE_REP",  topic, final_topic, serialize)
                        conn.send(len(msg).to_bytes(2, 'big')+msg)

                elif method == "CANCEL":
                    self.unsubscribe( topic, conn)

                elif method == "LIST_TOPICS":
                    msg=self.encode("LIST_TOPICS_REP", topic, self.list_topics(), serialize)
                    conn.send(len(msg).to_bytes(2, 'big')+msg)
            else:
                self.sele.unregister(conn)
                conn.close()
                self.sockets.pop(conn)


        


    def run(self):
        """Run until canceled."""

        while not self.canceled:
            events = self.sele.select()
            for key, mask in events:
                callback = key.data
                callback(key.fileobj, mask)
                
