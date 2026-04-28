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

    ExternalProject_Add(${target}
        SOURCE_DIR "${source_dir}"
        BINARY_DIR "${CMAKE_BINARY_DIR}/${target}"
        INSTALL_DIR "${CMAKE_INSTALL_PREFIX}"
        CMAKE_ARGS
            -DCMAKE_TOOLCHAIN_FILE:FILEPATH=${EMU68_DRIVER_STACK_TOOLCHAIN_FILE}
            -DCMAKE_INSTALL_PREFIX:PATH=${CMAKE_INSTALL_PREFIX}
            -DCMAKE_PREFIX_PATH:PATH=${CMAKE_INSTALL_PREFIX}
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

# Add all stack projects
add_stack_project(devicetree.resource "${DEVICETREE_RESOURCE_SOURCE_DIR}")
add_stack_project(mailbox.resource "${MAILBOX_RESOURCE_SOURCE_DIR}" DEPENDS devicetree.resource)
add_stack_project(emu68-common "${EMU68_COMMON_SOURCE_DIR}" DEPENDS devicetree.resource mailbox.resource)
add_stack_project(emu68-gic400-library "${EMU68_GIC400_SOURCE_DIR}" DEPENDS devicetree.resource)
add_stack_project(emu68-pcie-library "${EMU68_PCIE_SOURCE_DIR}" DEPENDS emu68-common emu68-gic400-library)
add_stack_project(emu68-xhci-driver "${EMU68_XHCI_SOURCE_DIR}" DEPENDS emu68-pcie-library)
add_stack_project(emu68-genet-driver "${EMU68_GENET_SOURCE_DIR}" DEPENDS emu68-common emu68-gic400-library)
add_stack_project(emu68-nvme-driver ${EMU68_NVME_SOURCE_DIR} DEPENDS emu68-pcie-library emu68-common)

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
# package target — creates emu68-drivers-<version>.zip for distribution.
# Uses cmake -E tar (built-in, no external tool required).
# The installer/ tree is bundled alongside the runtime binaries so Commodore
# Installer can be run directly from the archive.
# ---------------------------------------------------------------------------

set(PACKAGE_VERSION "${PROJECT_VERSION}")
set(PACKAGE_NAME    "emu68-drivers-${PACKAGE_VERSION}")
set(PACKAGE_DIR     "${CMAKE_BINARY_DIR}/package")
set(PACKAGE_STAGE   "${PACKAGE_DIR}/${PACKAGE_NAME}")
set(PACKAGE_ARCHIVE "${PACKAGE_DIR}/${PACKAGE_NAME}.zip")

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
    # Copy installer files
    COMMAND ${CMAKE_COMMAND} -E copy_directory
        "${CMAKE_CURRENT_SOURCE_DIR}/installer" "${PACKAGE_STAGE}"
    # Create the zip (chdir so the archive contains relative paths)
    COMMAND ${CMAKE_COMMAND} -E chdir "${PACKAGE_DIR}"
        ${CMAKE_COMMAND} -E tar cf "${PACKAGE_ARCHIVE}" --format=zip "${PACKAGE_NAME}/"
    WORKING_DIRECTORY "${CMAKE_BINARY_DIR}"
    COMMENT "Creating ${PACKAGE_NAME}.zip"
    VERBATIM
)