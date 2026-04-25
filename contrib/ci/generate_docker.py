#!/usr/bin/env python3
#
# Copyright 2017 Dell, Inc.
#
# SPDX-License-Identifier: LGPL-2.1-or-later
#

import os
import shutil
import subprocess
import sys

from fwupd_setup_helpers import parse_dependencies

# this is idiosyncratic for an amazing reason
RUNNER_ARCH_DEPS_MAP = {
    "ARM": "armhf",
    "ARM64": "aarch64",
    "X64": "x86_64",
    "X86": "i386",
}


def getenv_unwrap(name: str) -> str:
    val = os.getenv(name)
    if val is None:
        print(f"environment variable has not been set: '{name}'")
        sys.exit(1)
    else:
        return val


def get_container_cmd():
    """return docker or podman as container manager"""

    if shutil.which("docker"):
        return "docker"
    if shutil.which("podman"):
        return "podman"


directory = os.path.dirname(sys.argv[0])
MATRIX_CROSS = getenv_unwrap("MATRIX_CROSS")
MATRIX_DISTRO = getenv_unwrap("MATRIX_DISTRO")
RUNNER_ARCH = getenv_unwrap("RUNNER_ARCH")

template_file = os.path.join(directory, f"Dockerfile-{MATRIX_DISTRO}.in")
if not os.path.exists(template_file):
    print(f"Missing input file {template_file} for {MATRIX_DISTRO}")
    sys.exit(1)
with open(template_file) as file:
    content = file.read()


# special case for i386 and tartan debian container
match MATRIX_DISTRO:
    case "debian-i386":
        content = content.replace("FROM debian:testing", "FROM i386/debian:testing")
    case "debian-tartan":
        content = content.replace("FROM debian:testing", "FROM debian:unstable")


# insert commands to prepare cross compile
if MATRIX_CROSS:
    cross_setup = f"""\
    sed -i 's|Types: deb|Types: deb deb-src|' /etc/apt/sources.list.d/debian.sources; \\
    dpkg --add-architecture {MATRIX_CROSS};"""
else:
    cross_setup = "    "
content = content.replace("%%%SETUP%%%", cross_setup)


# insert dependencies to install
distro = MATRIX_DISTRO.split("-")[0]
if MATRIX_CROSS:
    deps = parse_dependencies(distro, MATRIX_CROSS, False, cross=True)
    deps += [f"crossbuild-essential-{MATRIX_CROSS}"]
elif MATRIX_DISTRO == "debian-i386":
    deps = parse_dependencies(distro, "i386", False)
else:
    deps = parse_dependencies(distro, RUNNER_ARCH_DEPS_MAP[RUNNER_ARCH], False)
deps = sorted(set(deps))
deps = [f"    {i}" for i in deps]
deps = " \\\n".join(deps)
content = content.replace("%%%DEPENDENCIES%%%", deps)


with open("Dockerfile", "w") as file:
    file.write(content)

if len(sys.argv) == 2 and sys.argv[1] == "build":
    cmd = get_container_cmd()
    args = [cmd, "build", "-t", f"fwupd-{MATRIX_DISTRO}"]
    if "http_proxy" in os.environ:
        args += [f"--build-arg=http_proxy={os.environ['http_proxy']}"]
    if "https_proxy" in os.environ:
        args += [f"--build-arg=https_proxy={os.environ['https_proxy']}"]
    args += ["-f", "./Dockerfile", "."]
    subprocess.check_call(args)
