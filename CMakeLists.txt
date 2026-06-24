cmake_minimum_required(VERSION 3.14)
project(emu68_driver_stack VERSION 1.0.2 LANGUAGES NONE)

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
    set(multiValueArgs DEPENDS)
    cmake_parse_arguments(STACK "${options}" "${oneValueArgs}" "${multiValueArgs}" ${ARGN})

    # Debug args only apply to debug-emitting components (those that consume
    # emu68-common's debug.h): the stack-wide backend, plus this component's
    # EMU68_DEBUG_HIGH boolean derived from the stack-wide component list.
    # devicetree.resource/mailbox.resource get neither — passing them would trip
    # CMake's "unused variable" warning.
    set(_debug_args "")
    if(target IN_LIST EMU68_DEBUG_COMPONENTS)
        set(_debug_high OFF)
        if(EMU68_DEBUG_HIGH STREQUAL "ALL" OR target IN_LIST EMU68_DEBUG_HIGH)
            set(_debug_high ON)
        endif()
        set(_debug_args
            -DEMU68_DEBUG_BACKEND:STRING=${EMU68_DEBUG_BACKEND}
            -DEMU68_DEBUG_HIGH:BOOL=${_debug_high})
    endif()

    ExternalProject_Add(${target}
        SOURCE_DIR "${source_dir}"
        BINARY_DIR "${CMAKE_BINARY_DIR}/${target}"
        INSTALL_DIR "${CMAKE_INSTALL_PREFIX}"
        CMAKE_ARGS
            -DCMAKE_TOOLCHAIN_FILE:FILEPATH=${EMU68_DRIVER_STACK_TOOLCHAIN_FILE}
            -DCMAKE_INSTALL_PREFIX:PATH=${CMAKE_INSTALL_PREFIX}
            -DCMAKE_PREFIX_PATH:PATH=${CMAKE_INSTALL_PREFIX}
            ${_debug_args}
        BUILD_COMMAND ${CMAKE_COMMAND} -E env PATH=${EMU68_TOOLCHAIN_BIN_DIR}:$ENV{PATH} ${CMAKE_COMMAND} --build <BINARY_DIR>
        INSTALL_COMMAND ${CMAKE_COMMAND} -E env PATH=${EMU68_TOOLCHAIN_BIN_DIR}:$ENV{PATH} ${CMAKE_COMMAND} --build <BINARY_DIR> --target install
        DEPENDS ${STACK_DEPENDS}
        USES_TERMINAL_CONFIGURE TRUE
        USES_TERMINAL_BUILD TRUE
        USES_TERMINAL_INSTALL TRUE
        CONFIGURE_HANDLED_BY_BUILD TRUE
        BUILD_ALWAYS TRUE
    )

    # Record the target so the aggregate 'stack' target can depend on the full
    # set without a hand-maintained list that has to be kept in sync.
    set_property(GLOBAL APPEND PROPERTY EMU68_STACK_TARGETS ${target})
endfunction()

# Add all stack projects.  Debug-emitting components additionally receive the
# stack-wide debug backend/level args, handled inside add_stack_project().
add_stack_project(devicetree.resource "${DEVICETREE_RESOURCE_SOURCE_DIR}")
add_stack_project(mailbox.resource "${MAILBOX_RESOURCE_SOURCE_DIR}" DEPENDS devicetree.resource)
add_stack_project(emu68-common "${EMU68_COMMON_SOURCE_DIR}" DEPENDS devicetree.resource mailbox.resource)
add_stack_project(emu68-gic400-library "${EMU68_GIC400_SOURCE_DIR}" DEPENDS devicetree.resource emu68-common)
add_stack_project(emu68-pcie-library "${EMU68_PCIE_SOURCE_DIR}" DEPENDS emu68-common emu68-gic400-library)
add_stack_project(emu68-xhci-driver "${EMU68_XHCI_SOURCE_DIR}" DEPENDS emu68-pcie-library)
add_stack_project(emu68-genet-driver "${EMU68_GENET_SOURCE_DIR}" DEPENDS emu68-common emu68-gic400-library)
add_stack_project(emu68-nvme-driver ${EMU68_NVME_SOURCE_DIR} DEPENDS emu68-pcie-library emu68-common)

get_property(_stack_targets GLOBAL PROPERTY EMU68_STACK_TARGETS)
add_custom_target(stack ALL DEPENDS ${_stack_targets})

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

emu68_read_version(COMMON_VERSION  "${EMU68_COMMON_SOURCE_DIR}/CMakeLists.txt")
emu68_read_version(GIC400_VERSION  "${EMU68_GIC400_SOURCE_DIR}/CMakeLists.txt")
emu68_read_version(BCMPCIE_VERSION "${EMU68_PCIE_SOURCE_DIR}/CMakeLists.txt")
emu68_read_version(OPENPCI_VERSION "${EMU68_PCIE_SOURCE_DIR}/openpci.library/CMakeLists.txt")
emu68_read_version(XHCI_VERSION    "${EMU68_XHCI_SOURCE_DIR}/CMakeLists.txt")
emu68_read_version(GENET_VERSION   "${EMU68_GENET_SOURCE_DIR}/CMakeLists.txt")
emu68_read_version(NVME_VERSION    "${EMU68_NVME_SOURCE_DIR}/CMakeLists.txt")

# Components whose README + LICENSE + release notes are bundled into the archive
# under Documentation/<name>/, and listed in the generated root 'Licenses' file.
# Fields: drawer-name | source dir | license summary | version variable.
# devicetree.resource / mailbox.resource are build-only and intentionally omitted.
set(EMU68_DOC_COMPONENTS
    "emu68-common|${EMU68_COMMON_SOURCE_DIR}|MPL-2.0 OR GPL-2.0+|COMMON_VERSION"
    "emu68-gic400-library|${EMU68_GIC400_SOURCE_DIR}|MPL-2.0 OR GPL-2.0+|GIC400_VERSION"
    "emu68-pcie-library|${EMU68_PCIE_SOURCE_DIR}|GPL-2.0 (bcmpcie/openpci/lspci)|BCMPCIE_VERSION"
    "emu68-xhci-driver|${EMU68_XHCI_SOURCE_DIR}|GPL-2.0|XHCI_VERSION"
    "emu68-genet-driver|${EMU68_GENET_SOURCE_DIR}|GPL-2.0 / MPL-2.0 (per-file SPDX)|GENET_VERSION"
    "emu68-nvme-driver|${EMU68_NVME_SOURCE_DIR}|GPL-2.0|NVME_VERSION")

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

# Root 'Licenses' summary — one entry per bundled component plus a binary->component
# map, so the archive is self-describing about licensing.  Versions reuse the
# values harvested above (single source of truth); per-file SPDX headers remain
# authoritative.
set(_licenses
"emu68 Driver Stack ${PACKAGE_VERSION} - component licenses\n\nEach component is covered by its own license; the full text ships in\nDocumentation/<component>/LICENSE.  Per-file SPDX headers are authoritative.\n\n")
foreach(_entry IN LISTS EMU68_DOC_COMPONENTS)
    string(REPLACE "|" ";" _parts "${_entry}")
    list(GET _parts 0 _name)
    list(GET _parts 2 _lic)
    list(GET _parts 3 _vervar)
    string(APPEND _licenses "  ${_name} ${${_vervar}}\n      ${_lic}\n      -> Documentation/${_name}/LICENSE\n\n")
endforeach()
string(APPEND _licenses
"Shipped binaries -> component:\n  gic400.library    -> emu68-gic400-library\n  bcmpcie.library   -> emu68-pcie-library\n  openpci.library   -> emu68-pcie-library\n  lspci             -> emu68-pcie-library\n  xhci.device       -> emu68-xhci-driver\n  genet.device      -> emu68-genet-driver\n  genet-stats       -> emu68-genet-driver\n  nvme.device       -> emu68-nvme-driver\n  nvmeinfo, nvmeadm -> emu68-nvme-driver\n\nemu68-common is a support library linked into the above; it ships no binary.\n")
file(WRITE "${CMAKE_BINARY_DIR}/installer/Licenses" "${_licenses}")

# Per-component documentation copy commands for the package target.  Each component
# contributes its LICENSE, README(s) and release notes to Documentation/<name>/.
# Developer-only README-internal.md is excluded; the file globs are resolved at
# configure time, so re-run CMake after adding a component doc file.
set(_doc_cmds)
foreach(_entry IN LISTS EMU68_DOC_COMPONENTS)
    string(REPLACE "|" ";" _parts "${_entry}")
    list(GET _parts 0 _name)
    list(GET _parts 1 _dir)
    set(_dest "${PACKAGE_STAGE}/Documentation/${_name}")
    list(APPEND _doc_cmds COMMAND ${CMAKE_COMMAND} -E make_directory "${_dest}")
    if(EXISTS "${_dir}/LICENSE")
        list(APPEND _doc_cmds COMMAND ${CMAKE_COMMAND} -E copy "${_dir}/LICENSE" "${_dest}/LICENSE")
    endif()
    file(GLOB _docs "${_dir}/README.md" "${_dir}/README-*.md" "${_dir}/RELEASE-NOTES*.md")
    foreach(_f IN LISTS _docs)
        get_filename_component(_fn "${_f}" NAME)
        if(_fn STREQUAL "README-internal.md")
            continue()
        endif()
        list(APPEND _doc_cmds COMMAND ${CMAKE_COMMAND} -E copy "${_f}" "${_dest}/${_fn}")
    endforeach()
endforeach()

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
    # Bundle each component's README/LICENSE/release notes under Documentation/,
    # plus the top-level changelog and the generated license summary at the root.
    ${_doc_cmds}
    COMMAND ${CMAKE_COMMAND} -E copy
        "${CMAKE_CURRENT_SOURCE_DIR}/RELEASE-NOTES.md" "${PACKAGE_STAGE}/RELEASE-NOTES.md"
    COMMAND ${CMAKE_COMMAND} -E copy
        "${CMAKE_BINARY_DIR}/installer/Licenses" "${PACKAGE_STAGE}/Licenses"
    # Create the LHA archive (chdir so paths inside are relative to the package root)
    COMMAND ${CMAKE_COMMAND} -E rm -f "${PACKAGE_ARCHIVE}"
    COMMAND ${CMAKE_COMMAND} -E chdir "${PACKAGE_DIR}"
        ${LHA_EXECUTABLE} a "${PACKAGE_NAME}.lha" "${PACKAGE_NAME}/"
    WORKING_DIRECTORY "${CMAKE_BINARY_DIR}"
    COMMENT "Creating ${PACKAGE_NAME}.lha"
    VERBATIM
)