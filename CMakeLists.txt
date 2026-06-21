cmake_minimum_required(VERSION 3.14)
project(emu68_driver_stack VERSION 1.0.0 LANGUAGES NONE)

include(ExternalProject)

# Set default install prefix
if(CMAKE_INSTALL_PREFIX_INITIALIZED_TO_DEFAULT)
    set(CMAKE_INSTALL_PREFIX "${CMAKE_CURRENT_SOURCE_DIR}/install" CACHE PATH "Driver stack install path" FORCE)
endif()

# Toolchain and toolchain bin dir
set(EMU68_DRIVER_STACK_TOOLCHAIN_FILE "${CMAKE_CURRENT_SOURCE_DIR}/cmake/toolchain.cmake" CACHE FILEPATH "Toolchain file used for all component builds")
set(EMU68_TOOLCHAIN_BIN_DIR "/opt/m68k-amigaos/bin" CACHE PATH "Directory added to PATH for component builds")

# Debug-output backend for the whole stack (see emu68-common/include/debug.h):
#   pistorm (default) - RawDoFmt -> magic 0xdeadbeef trap (Emu68/PiStorm). ROM-able.
#   serial            - debug.lib KPrintF -> console (serial @ 9600). Not ROM-able.
#   off               - debug fully compiled out.
# Propagated to every component below so a single backend is used consistently.
set(EMU68_DEBUG_BACKEND "pistorm" CACHE STRING "Debug output backend: pistorm | serial | off")
set_property(CACHE EMU68_DEBUG_BACKEND PROPERTY STRINGS pistorm serial off)

# Verbose ("high") debug logging (debug.h KprintfH / DEBUG_HIGH).  Independent of
# the backend, but requires DEBUG (i.e. backend != off) to actually emit anything.
# Value: a list of the stack component target names below to build with DEBUG_HIGH,
# or ALL for every debug-emitting component.  Empty (default) = off everywhere.
#   e.g. -DEMU68_DEBUG_HIGH=emu68-pcie-library
# Propagated per-component as a boolean by add_stack_project() below.
set(EMU68_DEBUG_HIGH "" CACHE STRING "Components to build with verbose DEBUG_HIGH logging (list, or ALL)")

# Components that emit debug output (consume emu68-common's debug.h); the only ones
# for which EMU68_DEBUG_HIGH is meaningful.  Used to reject typos in the list.
set(EMU68_DEBUG_COMPONENTS
    emu68-common
    emu68-gic400-library
    emu68-pcie-library
    emu68-xhci-driver
    emu68-genet-driver
    emu68-nvme-driver)

if(NOT EMU68_DEBUG_HIGH STREQUAL "ALL")
    foreach(_dh ${EMU68_DEBUG_HIGH})
        if(NOT _dh IN_LIST EMU68_DEBUG_COMPONENTS)
            message(FATAL_ERROR
                "EMU68_DEBUG_HIGH entry '${_dh}' is not a debug-emitting component.\n"
                "Valid values: ALL or any of: ${EMU68_DEBUG_COMPONENTS}")
        endif()
    endforeach()
endif()

# Default source directories point to the bundled submodules.
# Override any of these with -D<VAR>=/path/to/your/checkout for local development.
set(DEVICETREE_RESOURCE_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/components/devicetree.resource" CACHE PATH "Path to devicetree.resource sources")
set(MAILBOX_RESOURCE_SOURCE_DIR    "${CMAKE_CURRENT_SOURCE_DIR}/components/mailbox.resource"    CACHE PATH "Path to mailbox.resource sources")
set(EMU68_COMMON_SOURCE_DIR        "${CMAKE_CURRENT_SOURCE_DIR}/components/emu68-common"        CACHE PATH "Path to emu68-common sources")
set(EMU68_GIC400_SOURCE_DIR        "${CMAKE_CURRENT_SOURCE_DIR}/components/emu68-gic400-library" CACHE PATH "Path to emu68-gic400-library sources")
set(EMU68_PCIE_SOURCE_DIR          "${CMAKE_CURRENT_SOURCE_DIR}/components/emu68-pcie-library"  CACHE PATH "Path to emu68-pcie-library sources")
set(EMU68_XHCI_SOURCE_DIR          "${CMAKE_CURRENT_SOURCE_DIR}/components/emu68-xhci-driver"   CACHE PATH "Path to emu68-xhci-driver sources")
set(EMU68_GENET_SOURCE_DIR         "${CMAKE_CURRENT_SOURCE_DIR}/components/emu68-genet-driver"  CACHE PATH "Path to emu68-genet-driver sources")
set(EMU68_NVME_SOURCE_DIR          "${CMAKE_CURRENT_SOURCE_DIR}/components/emu68-nvme-driver"   CACHE PATH "Path to emu68-nvme-driver sources")

# Validate required paths
foreach(required_path
    EMU68_DRIVER_STACK_TOOLCHAIN_FILE
    DEVICETREE_RESOURCE_SOURCE_DIR
    MAILBOX_RESOURCE_SOURCE_DIR
    EMU68_COMMON_SOURCE_DIR
    EMU68_GIC400_SOURCE_DIR
    EMU68_PCIE_SOURCE_DIR
    EMU68_XHCI_SOURCE_DIR
    EMU68_GENET_SOURCE_DIR
    EMU68_NVME_SOURCE_DIR)
    if(NOT EXISTS "${${required_path}}")
        message(FATAL_ERROR
            "Required path does not exist: ${required_path}='${${required_path}}'\n"
            "If you cloned without submodules, run:\n"
            "  git submodule update --init --recursive\n"
            "Or override the path with -D${required_path}=/path/to/sources")
    endif()
endforeach()

# Validate toolchain bin dir
if(NOT EXISTS "${EMU68_TOOLCHAIN_BIN_DIR}")
    message(FATAL_ERROR "Toolchain bin directory does not exist: EMU68_TOOLCHAIN_BIN_DIR='${EMU68_TOOLCHAIN_BIN_DIR}'")
endif()

# Function to add stack projects
function(add_stack_project target source_dir)
    set(options)
    set(oneValueArgs)
    set(multiValueArgs DEPENDS EXTRA_CMAKE_ARGS)
    cmake_parse_arguments(STACK "${options}" "${oneValueArgs}" "${multiValueArgs}" ${ARGN})

    # Turn the stack-wide EMU68_DEBUG_HIGH component list into this component's
    # boolean.  Only pass it to debug-emitting components (those that consume
    # emu68-common's debug.h); handing it to the others (devicetree.resource/
    # mailbox.resource) trips CMake's "unused variable" warning.
    set(_debug_high_arg "")
    if(target IN_LIST EMU68_DEBUG_COMPONENTS)
        set(_debug_high OFF)
        if(EMU68_DEBUG_HIGH STREQUAL "ALL" OR target IN_LIST EMU68_DEBUG_HIGH)
            set(_debug_high ON)
        endif()
        set(_debug_high_arg -DEMU68_DEBUG_HIGH:BOOL=${_debug_high})
    endif()

    ExternalProject_Add(${target}
        SOURCE_DIR "${source_dir}"
        BINARY_DIR "${CMAKE_BINARY_DIR}/${target}"
        INSTALL_DIR "${CMAKE_INSTALL_PREFIX}"
        CMAKE_ARGS
            -DCMAKE_TOOLCHAIN_FILE:FILEPATH=${EMU68_DRIVER_STACK_TOOLCHAIN_FILE}
            -DCMAKE_INSTALL_PREFIX:PATH=${CMAKE_INSTALL_PREFIX}
            -DCMAKE_PREFIX_PATH:PATH=${CMAKE_INSTALL_PREFIX}
            ${_debug_high_arg}
            ${STACK_EXTRA_CMAKE_ARGS}
        BUILD_COMMAND ${CMAKE_COMMAND} -E env PATH=${EMU68_TOOLCHAIN_BIN_DIR}:$ENV{PATH} ${CMAKE_COMMAND} --build <BINARY_DIR>
        INSTALL_COMMAND ${CMAKE_COMMAND} -E env PATH=${EMU68_TOOLCHAIN_BIN_DIR}:$ENV{PATH} ${CMAKE_COMMAND} --build <BINARY_DIR> --target install
        DEPENDS ${STACK_DEPENDS}
        USES_TERMINAL_CONFIGURE TRUE
        USES_TERMINAL_BUILD TRUE
        USES_TERMINAL_INSTALL TRUE
        CONFIGURE_HANDLED_BY_BUILD TRUE
        BUILD_ALWAYS TRUE
    )
endfunction()

# Propagate the debug backend to every component that emits debug output (i.e.
# uses emu68-common's debug.h). devicetree.resource/mailbox.resource don't.
set(EMU68_DEBUG_ARGS EXTRA_CMAKE_ARGS -DEMU68_DEBUG_BACKEND:STRING=${EMU68_DEBUG_BACKEND})

# Add all stack projects
add_stack_project(devicetree.resource "${DEVICETREE_RESOURCE_SOURCE_DIR}")
add_stack_project(mailbox.resource "${MAILBOX_RESOURCE_SOURCE_DIR}" DEPENDS devicetree.resource)
add_stack_project(emu68-common "${EMU68_COMMON_SOURCE_DIR}" DEPENDS devicetree.resource mailbox.resource ${EMU68_DEBUG_ARGS})
add_stack_project(emu68-gic400-library "${EMU68_GIC400_SOURCE_DIR}" DEPENDS devicetree.resource emu68-common ${EMU68_DEBUG_ARGS})
add_stack_project(emu68-pcie-library "${EMU68_PCIE_SOURCE_DIR}" DEPENDS emu68-common emu68-gic400-library ${EMU68_DEBUG_ARGS})
add_stack_project(emu68-xhci-driver "${EMU68_XHCI_SOURCE_DIR}" DEPENDS emu68-pcie-library ${EMU68_DEBUG_ARGS})
add_stack_project(emu68-genet-driver "${EMU68_GENET_SOURCE_DIR}" DEPENDS emu68-common emu68-gic400-library ${EMU68_DEBUG_ARGS})
add_stack_project(emu68-nvme-driver ${EMU68_NVME_SOURCE_DIR} DEPENDS emu68-pcie-library emu68-common ${EMU68_DEBUG_ARGS})

add_custom_target(stack ALL
    DEPENDS
        devicetree.resource
        mailbox.resource
        emu68-common
        emu68-gic400-library
        emu68-pcie-library
        emu68-xhci-driver
        emu68-genet-driver
        emu68-nvme-driver
)

# ---------------------------------------------------------------------------
# package target — creates emu68-drivers-<version>.lha for distribution.
# the amigadev/crosstools image ships the archiver, and scripts/docker-build.sh
# builds inside that image.
# The installer/ tree is bundled alongside the runtime binaries so Commodore
# Installer can be run directly from the archive.
# ---------------------------------------------------------------------------

set(PACKAGE_VERSION "${PROJECT_VERSION}")

# Harvest each shipped binary's version from its component's project() so the
# generated ReadMe and the release notes can list them.  The component CMakeLists
# stays the single source of truth — we only parse, never duplicate the numbers.
# Authoritative file = the project() that carries the literal numeric version that
# is embedded into that binary (subdir projects inherit it via CMAKE_PROJECT_VERSION).
function(emu68_read_version out path)
    file(STRINGS "${path}" _lines REGEX "project[ \t]*\\(.*VERSION")
    list(GET _lines 0 _line)
    string(REGEX MATCH "VERSION[ \t]+([0-9]+(\\.[0-9]+)*)" _m "${_line}")
    set(${out} "${CMAKE_MATCH_1}" PARENT_SCOPE)
endfunction()

emu68_read_version(GIC400_VERSION  "${EMU68_GIC400_SOURCE_DIR}/CMakeLists.txt")
emu68_read_version(BCMPCIE_VERSION "${EMU68_PCIE_SOURCE_DIR}/CMakeLists.txt")
emu68_read_version(OPENPCI_VERSION "${EMU68_PCIE_SOURCE_DIR}/openpci.library/CMakeLists.txt")
emu68_read_version(XHCI_VERSION    "${EMU68_XHCI_SOURCE_DIR}/CMakeLists.txt")
emu68_read_version(GENET_VERSION   "${EMU68_GENET_SOURCE_DIR}/CMakeLists.txt")
emu68_read_version(NVME_VERSION    "${EMU68_NVME_SOURCE_DIR}/CMakeLists.txt")

# Describe the debug backend for the generated ReadMe so each archive is
# self-describing about which build variant it is.
set(DEBUG_BACKEND "${EMU68_DEBUG_BACKEND}")
if(EMU68_DEBUG_BACKEND STREQUAL "off")
    set(DEBUG_BACKEND_DESCRIPTION
        "Production build - driver debug output is disabled.")
elseif(EMU68_DEBUG_BACKEND STREQUAL "serial")
    set(DEBUG_BACKEND_DESCRIPTION
        "Debug build - driver debug output is sent to the Amiga serial port\n  (9600 baud) on real hardware, or can be captured/redirected on a host\n  with the Sashimi tool.")
else()
    set(DEBUG_BACKEND_DESCRIPTION
        "Debug build (${EMU68_DEBUG_BACKEND} backend) - driver debug output is routed\n  through the Emu68/PiStorm debug console.")
endif()

# Suffix the package name by backend so a release can ship multiple variants
# side by side.  'off' is the production download and carries no suffix.
if(EMU68_DEBUG_BACKEND STREQUAL "off")
    set(PACKAGE_SUFFIX "")
elseif(EMU68_DEBUG_BACKEND STREQUAL "serial")
    set(PACKAGE_SUFFIX "-serial")
else()
    set(PACKAGE_SUFFIX "-${EMU68_DEBUG_BACKEND}")
endif()

set(PACKAGE_NAME    "emu68-drivers-${PACKAGE_VERSION}${PACKAGE_SUFFIX}")
set(PACKAGE_DIR     "${CMAKE_BINARY_DIR}/package")
set(PACKAGE_STAGE   "${PACKAGE_DIR}/${PACKAGE_NAME}")
set(PACKAGE_ARCHIVE "${PACKAGE_DIR}/${PACKAGE_NAME}.lha")

# Locate the LHA archiver.  The toolchain image provides it; a native build
# without lha can still build the drivers — only the 'package' target needs it,
# so warn (don't fail) here and let the target itself fail if it is run.
find_program(LHA_EXECUTABLE lha)
if(NOT LHA_EXECUTABLE)
    message(WARNING
        "lha archiver not found: the 'package' target will fail if run.\n"
        "Build/package via scripts/docker-build.sh (the toolchain image ships lha), "
        "or install an lha archiver.")
    set(LHA_EXECUTABLE lha)
endif()

# Stamp the package version into the installer files — single source of truth is
# PROJECT_VERSION.  The .in templates carry the @PACKAGE_VERSION@ placeholder.
configure_file(
    "${CMAKE_CURRENT_SOURCE_DIR}/installer/Install.in"
    "${CMAKE_BINARY_DIR}/installer/Install"
    @ONLY)
configure_file(
    "${CMAKE_CURRENT_SOURCE_DIR}/installer/ReadMe.in"
    "${CMAKE_BINARY_DIR}/installer/ReadMe"
    @ONLY)

# Plain-text component-version manifest, reused as the GitHub release body so the
# release notes carry the same versions the ReadMe shows (single generation).
file(WRITE "${CMAKE_BINARY_DIR}/installer/VERSIONS.txt"
"emu68 Driver Stack ${PACKAGE_VERSION} - component versions:

  gic400.library    ${GIC400_VERSION}
  bcmpcie.library   ${BCMPCIE_VERSION}
  xhci.device       ${XHCI_VERSION}
  genet.device      ${GENET_VERSION}
  nvme.device       ${NVME_VERSION}
  openpci.library   ${OPENPCI_VERSION}
")

add_custom_target(package
    DEPENDS stack
    COMMAND ${CMAKE_COMMAND} -E rm -rf "${PACKAGE_STAGE}"
    COMMAND ${CMAKE_COMMAND} -E make_directory "${PACKAGE_STAGE}"
    # Copy runtime directories
    COMMAND ${CMAKE_COMMAND} -E copy_directory
        "${CMAKE_INSTALL_PREFIX}/LIBS" "${PACKAGE_STAGE}/LIBS"
    COMMAND ${CMAKE_COMMAND} -E copy_directory
        "${CMAKE_INSTALL_PREFIX}/DEVS" "${PACKAGE_STAGE}/DEVS"
    COMMAND ${CMAKE_COMMAND} -E copy_directory
        "${CMAKE_INSTALL_PREFIX}/C"    "${PACKAGE_STAGE}/C"
    # Copy installer files, then swap in the version-stamped Install/ReadMe (the
    # source tree carries the .in templates; the generated files replace them).
    COMMAND ${CMAKE_COMMAND} -E copy_directory
        "${CMAKE_CURRENT_SOURCE_DIR}/installer" "${PACKAGE_STAGE}"
    COMMAND ${CMAKE_COMMAND} -E rm -f "${PACKAGE_STAGE}/Install.in" "${PACKAGE_STAGE}/ReadMe.in"
    COMMAND ${CMAKE_COMMAND} -E copy
        "${CMAKE_BINARY_DIR}/installer/Install" "${PACKAGE_STAGE}/Install"
    COMMAND ${CMAKE_COMMAND} -E copy
        "${CMAKE_BINARY_DIR}/installer/ReadMe" "${PACKAGE_STAGE}/ReadMe"
    # Create the LHA archive (chdir so paths inside are relative to the package root)
    COMMAND ${CMAKE_COMMAND} -E rm -f "${PACKAGE_ARCHIVE}"
    COMMAND ${CMAKE_COMMAND} -E chdir "${PACKAGE_DIR}"
        ${LHA_EXECUTABLE} a "${PACKAGE_NAME}.lha" "${PACKAGE_NAME}/"
    WORKING_DIRECTORY "${CMAKE_BINARY_DIR}"
    COMMENT "Creating ${PACKAGE_NAME}.lha"
    VERBATIM
)