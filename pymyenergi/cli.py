import argparse
import asyncio
import json
import logging
import sys
from getpass import getpass

from pymyenergi.client import device_factory
from pymyenergi.client import MyenergiClient
from pymyenergi.connection import Connection
from pymyenergi.exceptions import WrongCredentials
from pymyenergi.zappi import CHARGE_MODES

from . import HARVI

logging.basicConfig()
logging.root.setLevel(logging.WARNING)


async def main(args):
    username = args.username or input("Please enter your hub serial number: ")
    password = args.password or getpass()
    conn = Connection(username, password)
    if args.debug:
        logging.root.setLevel(logging.DEBUG)
    try:
        if args.command == "list":
            client = MyenergiClient(conn)
            devices = await client.get_devices(args.kind)
            for device in devices:
                if args.json:
                    print(json.dumps(device.data, indent=2))
                else:
                    print(device.show())
        elif args.command == "overview":
            client = MyenergiClient(conn)
            devices = await client.get_devices()
            await client.refresh_history_today()
            out = f"Site name: {client.site_name}\n"
            out = out + f"Home consumption : {client.consumption_home}W\n"
            out = out + f"Power grid       : {client.power_grid}W\n"
            out = out + f"Power generation : {client.power_generation}W\n"
            out = out + f"Power EV charge  : {client.power_charging}W\n"
            out = out + f"Power battery    : {client.power_battery}W\n"
            out = out + f"Energy imported  : {client.energy_imported/1000:.2f}kWh\n"
            out = out + f"Energy exported  : {client.energy_exported/1000:.2f}kWh\n"
            out = out + f"Energy generated : {client.energy_generated/1000:.2f}kWh\n"
            out = out + f"Energy diverted  : {client.energy_diverted/1000:.2f}kWh\n"
            out = out + "Devices:\n"
            for device in devices:
                out = out + f"  {device.kind.capitalize()}: {device.name}"
                if device.kind != HARVI:
                    out = out + f"\t{device.energy_total}Wh today"
                out = out + "\n"
            print(out)
        elif args.command in ["zappi", "eddi", "harvi"]:
            device = device_factory(conn, args.command, args.serial)
            await device.refresh()
            if args.action == "show":
                if args.json:
                    print(json.dumps(device.data, indent=2))
                else:
                    print(device.show())
            elif args.action == "energy":
                data = await device.energy_today()
                if args.json:
                    print(json.dumps(data, indent=2))
                else:
                    for key in data.keys():
                        print(f"{key}: {(data[key]/1000):.2f}kWh")
            elif args.action == "stop" and args.command == "zappi":
                await device.stop_charge()
                print("Charging was stopped")
            elif args.action == "mode" and args.command == "zappi":
                if len(args.arg) < 1 or args.arg[0].capitalize() not in CHARGE_MODES:
                    modes = ", ".join(CHARGE_MODES)
                    sys.exit(f"A mode must be specifed, one of {modes}")
                await device.set_charge_mode(args.arg[0])
                print(f"Charging was set to {args.arg[0].capitalize()}")
            elif args.action == "mingreen" and args.command == "zappi":
                if len(args.arg) < 1:
                    sys.exit("A minimum green level must be provided")
                await device.set_minimum_green_level(args.arg[0])
                print(f"Minimum green level was set to {args.arg[0]}")
            elif args.action == "boost" and args.command == "zappi":
                await device.start_boost(args.arg[0])
                print(f"Start boosting with {args.arg[0]}kWh")
            elif args.action == "smart-boost" and args.command == "zappi":
                await device.start_smart_boost(args.arg[0], args.arg[1])
                print(
                    f"Start smart boosting with {args.arg[0]}kWh complete by {args.arg[1]}"
                )
        else:
            sys.exit("A serial number is needed")
    except WrongCredentials:
        sys.exit("Wrong username or password")


def cli():
    parser = argparse.ArgumentParser(prog="myenergi", description="myenergi CLI.")
    parser.add_argument("-u", "--username", dest="username", default=None)
    parser.add_argument("-p", "--password", dest="password", default=None)
    parser.add_argument("-d", "--debug", dest="debug", action="store_true")
    parser.add_argument("-j", "--json", dest="json", action="store_true", default=False)
    subparsers = parser.add_subparsers(dest="command", help="sub-command help")
    subparser_list = subparsers.add_parser("list", help="list help")
    subparser_list.add_argument("-k", "--kind", dest="kind", default="all")
    subparsers.add_parser("overview", help="overview help")
    subparsers.add_parser("energy", help="energy help")
    subparser_zappi = subparsers.add_parser("zappi", help="zappi help")
    subparser_zappi.add_argument("serial", default=None)
    subparser_zappi.add_argument(
        "action",
        choices=["show", "energy", "stop", "mode", "boost", "smart-boost", "mingreen"],
    )
    subparser_zappi.add_argument("arg", nargs="*")
    subparser_eddi = subparsers.add_parser("eddi", help="eddi help")
    subparser_eddi.add_argument("serial", default=None)
    subparser_eddi.add_argument("action", choices=["show", "energy"])
    subparser_eddi.add_argument("arg", nargs="*")

    subparser_harvi = subparsers.add_parser("harvi", help="harvi help")
    subparser_harvi.add_argument("serial", default=None)
    subparser_harvi.add_argument("action", choices=["show"])
    subparser_harvi.add_argument("arg", nargs="*")

    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(args))
