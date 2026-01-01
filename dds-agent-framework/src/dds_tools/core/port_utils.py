"""Port and domain ID utilities for DDS testing.

This module provides utilities for managing DDS domain IDs and ports,
helping avoid conflicts in test environments.
"""

import os
import random
import socket
from dataclasses import dataclass


@dataclass
class DomainPorts:
    """RTPS port numbers for a DDS domain."""

    domain_id: int
    discovery_multicast: int
    discovery_unicast: int
    user_multicast: int
    user_unicast: int


def calculate_rtps_ports(domain_id: int, participant_id: int = 0) -> DomainPorts:
    """Calculate RTPS port numbers for a domain ID.

    RTI Connext DDS uses the following port formula (per RTPS spec):
    - Discovery Multicast: PB + DG * domainId + d0
    - Discovery Unicast: PB + DG * domainId + d1 + PG * participantId
    - User Multicast: PB + DG * domainId + d2
    - User Unicast: PB + DG * domainId + d3 + PG * participantId

    Where (for RTI defaults):
    - PB (Port Base) = 7400
    - DG (Domain ID Gain) = 250
    - PG (Participant ID Gain) = 2
    - d0 = 0, d1 = 10, d2 = 1, d3 = 11

    Args:
        domain_id: The DDS domain ID.
        participant_id: The participant ID within the domain.

    Returns:
        DomainPorts with calculated port numbers.
    """
    PB = 7400  # Port Base
    DG = 250   # Domain ID Gain
    PG = 2     # Participant ID Gain
    d0, d1, d2, d3 = 0, 10, 1, 11

    base = PB + DG * domain_id

    return DomainPorts(
        domain_id=domain_id,
        discovery_multicast=base + d0,
        discovery_unicast=base + d1 + PG * participant_id,
        user_multicast=base + d2,
        user_unicast=base + d3 + PG * participant_id,
    )


def is_port_available(port: int, host: str = "0.0.0.0") -> bool:
    """Check if a port is available for binding.

    Args:
        port: Port number to check.
        host: Host address to check on.

    Returns:
        True if the port is available.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind((host, port))
            return True
    except OSError:
        return False


def is_domain_available(domain_id: int, participant_id: int = 0) -> bool:
    """Check if a DDS domain ID is available (ports not in use).

    Args:
        domain_id: The DDS domain ID to check.
        participant_id: The participant ID to check.

    Returns:
        True if all required ports are available.
    """
    ports = calculate_rtps_ports(domain_id, participant_id)

    # Check all ports
    for port in [
        ports.discovery_multicast,
        ports.discovery_unicast,
        ports.user_multicast,
        ports.user_unicast,
    ]:
        if not is_port_available(port):
            return False

    return True


def find_available_domain(
    start: int = 50,
    end: int = 100,
    participant_id: int = 0,
) -> int | None:
    """Find an available DDS domain ID.

    Searches for a domain ID where all required RTPS ports are available.
    Avoids high domain IDs that can cause RTPS port overflow.

    Args:
        start: Starting domain ID to search from.
        end: Ending domain ID (exclusive).
        participant_id: Participant ID to check.

    Returns:
        An available domain ID, or None if none found.
    """
    # Shuffle to reduce collision probability in parallel tests
    domain_ids = list(range(start, end))
    random.shuffle(domain_ids)

    for domain_id in domain_ids:
        if is_domain_available(domain_id, participant_id):
            return domain_id

    return None


def get_safe_domain_id() -> int:
    """Get a safe domain ID for testing.

    This function tries to find an available domain ID, falling back
    to a random ID in a safe range if port checking fails.

    Returns:
        A domain ID suitable for testing.
    """
    # First, try to find an actually available domain
    available = find_available_domain(start=50, end=99)
    if available is not None:
        return available

    # Fall back to random in a safe range
    return random.randint(50, 99)


def validate_domain_id(domain_id: int) -> tuple[bool, str]:
    """Validate a domain ID for use with RTI Connext DDS.

    Args:
        domain_id: The domain ID to validate.

    Returns:
        Tuple of (is_valid, message).
    """
    if domain_id < 0:
        return False, "Domain ID cannot be negative"

    if domain_id > 232:
        # With default port settings, domain IDs > 232 cause port overflow
        # (7400 + 250 * 233 = 65650 > 65535)
        return False, f"Domain ID {domain_id} is too high (max safe value: 232)"

    # Calculate highest port
    ports = calculate_rtps_ports(domain_id, participant_id=119)  # Max participants
    max_port = max(
        ports.discovery_multicast,
        ports.discovery_unicast,
        ports.user_multicast,
        ports.user_unicast,
    )

    if max_port > 65535:
        return False, f"Domain ID {domain_id} would use invalid port {max_port}"

    return True, "OK"

