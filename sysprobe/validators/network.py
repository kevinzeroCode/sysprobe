import ipaddress


def parse_active_ipv4_interfaces(output: str) -> tuple[str, ...]:
    """Parse interface names from one-line global IPv4 address records."""

    interfaces: list[str] = []
    for line in output.splitlines():
        if not line.strip():
            continue

        fields = line.split()
        try:
            index_text, interface_name, family, address = fields[:4]
            index = int(index_text.removesuffix(":"))
            if (
                not index_text.endswith(":")
                or index <= 0
                or family != "inet"
                or "/" not in address
            ):
                raise ValueError
            ipaddress.IPv4Interface(address)
        except (ValueError, IndexError) as error:
            raise ValueError("malformed IPv4 interface output") from error

        if interface_name not in interfaces:
            interfaces.append(interface_name)

    return tuple(interfaces)


def parse_default_route_interfaces(output: str) -> tuple[str, ...]:
    """Parse device names from default IPv4 route records."""

    interfaces: list[str] = []
    for line in output.splitlines():
        if not line.strip():
            continue

        fields = line.split()
        try:
            if fields[0] != "default":
                raise ValueError

            for position, field in enumerate(fields):
                if field == "via":
                    ipaddress.IPv4Address(fields[position + 1])

            device_positions = [
                position
                for position, field in enumerate(fields)
                if field == "dev"
            ]
            if not device_positions:
                raise ValueError

            devices = [fields[position + 1] for position in device_positions]
        except (ValueError, IndexError) as error:
            raise ValueError("malformed default IPv4 route output") from error

        for interface_name in devices:
            if interface_name not in interfaces:
                interfaces.append(interface_name)

    return tuple(interfaces)
