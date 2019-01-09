import logging
import sys
import argparse
from datetime import datetime, timedelta
import math
import time

try:
    from IPython import embed
except ImportError:
    import code

    def embed():
        code.interact(local=dict(globals(), **locals()))

from my_opcua import ua
from my_opcua import Client
from my_opcua import Server
from my_opcua import Node
from my_opcua import uamethod
from my_opcua.ua.uaerrors import UaStatusCodeError

from contextlib import suppress


def add_minimum_args(parser):
    parser.add_argument("-u",
                        "--url",
                        help="URL of OPC UA server (for example: opc.tcp://example.org:4840)",
                        default='opc.tcp://localhost:4840',
                        metavar="URL")
    parser.add_argument("-v",
                        "--verbose",
                        dest="loglevel",
                        choices=['DEBUG', 'INFO',
                                 'WARNING', 'ERROR', 'CRITICAL'],
                        default='WARNING',
                        help="Set log level")
    parser.add_argument("--timeout",
                        dest="timeout",
                        type=int,
                        default=1,
                        help="Set socket timeout (NOT the diverse UA timeouts)")


def add_common_args(parser, default_node='i=84', require_node=False):
    add_minimum_args(parser)
    parser.add_argument("-n",
                        "--nodeid",
                        help="Fully-qualified node ID (for example: i=85). Default: root node",
                        default=default_node,
                        required=False,
                        metavar="NODE")
    parser.add_argument("-p",
                        "--path",
                        help="Comma separated browse path to the node starting at NODE (for example: 3:Mybject,3:MyVariable)",
                        default='',
                        metavar="BROWSEPATH")
    parser.add_argument("-i",
                        "--namespace",
                        help="Default namespace",
                        type=int,
                        default=0,
                        metavar="NAMESPACE")
    parser.add_argument("--security",
                        help="Security settings, for example: Basic256,SignAndEncrypt,cert.der,pk.pem[,server_cert.der]. Default: None",
                        default='')
    parser.add_argument("--user",
                        help="User name for authentication. Overrides the user name given in the URL.")
    parser.add_argument("--password",
                        help="Password name for authentication. Overrides the password given in the URL.")


def _require_nodeid(parser, args):
    return
    # check that a nodeid has been given explicitly, a bit hackish...
    if args.nodeid == "i=84" and args.path == "":
        parser.print_usage()
        print("{0}: error: A NodeId or BrowsePath is required".format(parser.prog))
        sys.exit(1)


def parse_args(parser, requirenodeid=False):
    args = parser.parse_args()
    logging.basicConfig(format="%(levelname)s: %(message)s",
                        level=getattr(logging, args.loglevel))
    if args.url and '://' not in args.url:
        logging.info("Adding default scheme %s to URL %s",
                     ua.OPC_TCP_SCHEME, args.url)
        args.url = ua.OPC_TCP_SCHEME + '://' + args.url
    if requirenodeid:
        _require_nodeid(parser, args)
    return args


def get_node(client, args):
    node = client.get_node(args.nodeid)
    path = '0:Objects, 2:DeviceSet, 4:rfr310'.split(",")
    if node.nodeid == ua.NodeId(84, 0) and path[0] == "0:Root":
        # let user specify root if not node given
        path = path[1:]
    node = node.get_child(path)
    return node


def _args_to_array(val, array):
    if array == "guess":
        if "," in val:
            array = "true"
    if array == "true":
        val = val.split(",")
    return val


def _arg_to_bool(val):
    return val in ("true", "True")


def _arg_to_variant(val, array, ptype, varianttype=None):
    val = _args_to_array(val, array)
    if isinstance(val, list):
        val = [ptype(i) for i in val]
    else:
        val = ptype(val)
    if varianttype:
        return ua.Variant(val, varianttype)
    else:
        return ua.Variant(val)


def _val_to_variant(val, args):
    array = args.array
    if args.datatype == "guess":
        if val in ("true", "True", "false", "False"):
            return _arg_to_variant(val, array, _arg_to_bool)
        try:
            return _arg_to_variant(val, array, int)
        except ValueError:
            try:
                return _arg_to_variant(val, array, float)
            except ValueError:
                return _arg_to_variant(val, array, str)
    elif args.datatype == "bool":
        if val in ("1", "True", "true"):
            return ua.Variant(True, ua.VariantType.Boolean)
        else:
            return ua.Variant(False, ua.VariantType.Boolean)
    elif args.datatype == "sbyte":
        return _arg_to_variant(val, array, int, ua.VariantType.SByte)
    elif args.datatype == "byte":
        return _arg_to_variant(val, array, int, ua.VariantType.Byte)
    # elif args.datatype == "uint8":
        # return _arg_to_variant(val, array, int, ua.VariantType.Byte)
    elif args.datatype == "uint16":
        return _arg_to_variant(val, array, int, ua.VariantType.UInt16)
    elif args.datatype == "uint32":
        return _arg_to_variant(val, array, int, ua.VariantType.UInt32)
    elif args.datatype == "uint64":
        return _arg_to_variant(val, array, int, ua.VariantType.UInt64)
    # elif args.datatype == "int8":
        # return ua.Variant(int(val), ua.VariantType.Int8)
    elif args.datatype == "int16":
        return _arg_to_variant(val, array, int, ua.VariantType.Int16)
    elif args.datatype == "int32":
        return _arg_to_variant(val, array, int, ua.VariantType.Int32)
    elif args.datatype == "int64":
        return _arg_to_variant(val, array, int, ua.VariantType.Int64)
    elif args.datatype == "float":
        return _arg_to_variant(val, array, float, ua.VariantType.Float)
    elif args.datatype == "double":
        return _arg_to_variant(val, array, float, ua.VariantType.Double)
    elif args.datatype == "string":
        return _arg_to_variant(val, array, str, ua.VariantType.String)
    elif args.datatype == "datetime":
        raise NotImplementedError
    elif args.datatype == "Guid":
        return _arg_to_variant(val, array, bytes, ua.VariantType.Guid)
    elif args.datatype == "ByteString":
        return _arg_to_variant(val, array, bytes, ua.VariantType.ByteString)
    elif args.datatype == "xml":
        return _arg_to_variant(val, array, str, ua.VariantType.XmlElement)
    elif args.datatype == "nodeid":
        return _arg_to_variant(val, array, ua.NodeId.from_string, ua.VariantType.NodeId)
    elif args.datatype == "expandednodeid":
        return _arg_to_variant(val, array, ua.ExpandedNodeId.from_string, ua.VariantType.ExpandedNodeId)
    elif args.datatype == "statuscode":
        return _arg_to_variant(val, array, int, ua.VariantType.StatusCode)
    elif args.datatype in ("qualifiedname", "browsename"):
        return _arg_to_variant(val, array, ua.QualifiedName.from_string, ua.VariantType.QualifiedName)
    elif args.datatype == "LocalizedText":
        return _arg_to_variant(val, array, ua.LocalizedText, ua.VariantType.LocalizedText)


def _configure_client_with_args(client, args):
    if args.user:
        client.set_user(args.user)
    if args.password:
        client.set_password(args.password)
    client.set_security_string(args.security)


def prepare():
    parser = argparse.ArgumentParser(description="Call method of a node")
    add_common_args(parser)
    parser.add_argument("-m",
                        "--method",
                        dest="method",
                        type=int,
                        default=None,
                        help="Set method to call. If not given then (single) method of the selected node is used.")
    parser.add_argument("-l",
                        "--list",
                        "--array",
                        dest="array",
                        default="guess",
                        choices=["guess", "true", "false"],
                        help="Value is an array")
    parser.add_argument("-t",
                        "--datatype",
                        dest="datatype",
                        default="guess",
                        choices=["guess", 'byte', 'sbyte', 'nodeid', 'expandednodeid', 'qualifiedname', 'browsename', 'string', 'float', 'double', 'int16',
                                 'int32', "int64", 'uint16', 'uint32', 'uint64', "bool", "string", 'datetime', 'bytestring', 'xmlelement', 'statuscode', 'localizedtext'],
                        help="Data type to return")
    parser.add_argument("value",
                        help="Value to use for call to method, if any",
                        nargs="?",
                        metavar="VALUE")

    args = parse_args(parser, requirenodeid=True)

    client = Client('opc.tcp://10.10.10.13:4840', timeout=args.timeout)
    _configure_client_with_args(client, args)
    client.connect()
    try:
        node = get_node(client, args)
        val = (_val_to_variant('magicwordxx', args),)

        # determine method to call: Either explicitly given or automatically select the method of the selected node.
        methods = node.get_methods()
        method_id = None
        #print( "methods=%s" % (methods) )

        if (args.method is None):
            if (len(methods) == 0):
                raise ValueError(
                    "No methods in selected node and no method given")
            elif (len(methods) == 1):
                method_id = methods[0]
            else:
                method_id = methods[0]  # This should be scan? TODO
        else:
            for m in methods:
                if (m.nodeid.Identifier == args.method):
                    method_id = m.nodeid
                    break

        if (method_id is None):
            # last resort:
            # , namespaceidx=? )#, nodeidtype=?): )
            method_id = ua.NodeId(identifier=args.method)

        #print( "method_id=%s\nval=%s" % (method_id,val) )

        # for _ in range(1):
        #    with suppress(Exception):
        return client, node, method_id, val
    finally:
        pass


def call_read(node, method_id, val):
    result_variants = node.call_method(method_id, *val)
    ids = []
    for res in result_variants[0]:
        ids.append(res.Body.hex()[50:][:24])
    return ids


if __name__ == "__main__":
    client, node, method_id, val = prepare()

    try:
        ids = call_read(node, method_id, val)
        print(ids)
    finally:
        client.disconnect()
