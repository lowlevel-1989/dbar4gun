import argparse

parser = argparse.ArgumentParser()

subparsers = parser.add_subparsers(dest="command")

parser.add_argument("--width",  type=int)
parser.add_argument("--height", type=int)

command_start   = subparsers.add_parser("start")
command_stop    = subparsers.add_parser("stop")
command_version = subparsers.add_parser("version")
command_gui     = subparsers.add_parser("gui")

command_start.add_argument("--width",  type=int)
command_start.add_argument("--height", type=int)

command_gui.add_argument("--width",  type=int)
command_gui.add_argument("--height", type=int)


config = parser.parse_args()

command = "start"
if config.command:
    command = config.command

print(config)
