"""``python -m gateway serve`` runs the gateway; ``python -m gateway simulate`` plays a [SIM] scenario against it."""

import argparse
import logging
import os
import signal
import sys
import threading
from types import FrameType

from gateway import sim
from gateway.config import ConfigError, Settings
from gateway.forwarder import Forwarder
from gateway.queue import Queue
from gateway.server import make_server


def serve() -> int:
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        print(f"configuration: {exc}", file=sys.stderr)
        return 2
    queue = Queue(settings.queue_path, settings.queue_max)
    forwarder = Forwarder(settings, queue)
    server = make_server(settings, queue)
    worker = threading.Thread(target=forwarder.run, name="forwarder", daemon=True)
    worker.start()

    def stop(_signum: int, _frame: FrameType | None) -> None:
        forwarder.stop()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    logging.getLogger("gateway").info("listening on %s:%d", settings.bind, settings.port)
    server.serve_forever()
    worker.join(timeout=settings.timeout_s)
    forwarder.flush_once()
    queue.close()
    return 0


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("GATEWAY_LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s"
    )
    parser = argparse.ArgumentParser(prog="gateway")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve", help="receive the sensors' readings and relay them to the API")
    sim_parser = sub.add_parser("simulate", help="[SIM] play a scenario with the sensors of SIM_SENSORS")
    sim_parser.add_argument("--gateway", default="http://127.0.0.1:8088")
    sim_parser.add_argument("--scenario", choices=sorted(sim.SCENARIOS), default="storm")
    sim_parser.add_argument("--steps", type=int, default=12)
    sim_parser.add_argument("--every", type=float, default=5.0)
    args = parser.parse_args()
    if args.command == "serve":
        return serve()
    sensors = sim.parse_sensors(os.environ.get("SIM_SENSORS", ""))
    sim.run(args.gateway, sensors, args.scenario, max(args.steps, 2), args.every)
    return 0


if __name__ == "__main__":
    sys.exit(main())
