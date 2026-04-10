cmake_minimum_required(VERSION 3.14)
project(emu68_driver_stack NONE)

include(ExternalProject)

if(CMAKE_INSTALL_PREFIX_INITIALIZED_TO_DEFAULT)
    set(CMAKE_INSTALL_PREFIX "${CMAKE_CURRENT_SOURCE_DIR}/install" CACHE PATH "Driver stack install path" FORCE)
endif()

get_filename_component(EMU68_STACK_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/.." ABSOLUTE)
set(EMU68_STACK_ROOT "${EMU68_STACK_ROOT}" CACHE PATH "Root directory containing the Emu68 component repositories")
set(EMU68_DRIVER_STACK_TOOLCHAIN_FILE "${CMAKE_CURRENT_SOURCE_DIR}/cmake/toolchain.cmake" CACHE FILEPATH "Toolchain file used for all component builds")
set(EMU68_TOOLCHAIN_BIN_DIR "/opt/m68k-amigaos/bin" CACHE PATH "Directory added to PATH for component builds")

set(DEVICETREE_RESOURCE_SOURCE_DIR "${EMU68_STACK_ROOT}/devicetree.resource" CACHE PATH "Path to devicetree.resource sources")
set(MAILBOX_RESOURCE_SOURCE_DIR "${EMU68_STACK_ROOT}/mailbox.resource" CACHE PATH "Path to mailbox.resource sources")
set(EMU68_COMMON_SOURCE_DIR "${EMU68_STACK_ROOT}/emu68-common" CACHE PATH "Path to emu68-common sources")
set(EMU68_GIC400_SOURCE_DIR "${EMU68_STACK_ROOT}/emu68-gic400-library" CACHE PATH "Path to emu68-gic400-library sources")
set(EMU68_PCIE_SOURCE_DIR "${EMU68_STACK_ROOT}/emu68-pcie-library" CACHE PATH "Path to emu68-pcie-library sources")
set(EMU68_XHCI_SOURCE_DIR "${EMU68_STACK_ROOT}/emu68-xhci-driver" CACHE PATH "Path to emu68-xhci-driver sources")
set(EMU68_GENET_SOURCE_DIR "${EMU68_STACK_ROOT}/emu68-genet-driver" CACHE PATH "Path to emu68-genet-driver sources")

foreach(required_path
    EMU68_DRIVER_STACK_TOOLCHAIN_FILE
        DEVICETREE_RESOURCE_SOURCE_DIR
        MAILBOX_RESOURCE_SOURCE_DIR
        EMU68_COMMON_SOURCE_DIR
        EMU68_GIC400_SOURCE_DIR
        EMU68_PCIE_SOURCE_DIR
        EMU68_XHCI_SOURCE_DIR
        EMU68_GENET_SOURCE_DIR)
    if(NOT EXISTS "${${required_path}}")
        message(FATAL_ERROR "Required path does not exist: ${required_path}='${${required_path}}'")
    endif()
endforeach()

if(NOT EXISTS "${EMU68_TOOLCHAIN_BIN_DIR}")
    message(FATAL_ERROR "Toolchain bin directory does not exist: EMU68_TOOLCHAIN_BIN_DIR='${EMU68_TOOLCHAIN_BIN_DIR}'")
endif()

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

add_stack_project(devicetree.resource "${DEVICETREE_RESOURCE_SOURCE_DIR}")
add_stack_project(mailbox.resource "${MAILBOX_RESOURCE_SOURCE_DIR}" DEPENDS devicetree.resource)
add_stack_project(emu68-common "${EMU68_COMMON_SOURCE_DIR}" DEPENDS devicetree.resource mailbox.resource)
add_stack_project(emu68-gic400-library "${EMU68_GIC400_SOURCE_DIR}" DEPENDS devicetree.resource)
add_stack_project(emu68-pcie-library "${EMU68_PCIE_SOURCE_DIR}" DEPENDS emu68-common emu68-gic400-library)
add_stack_project(emu68-xhci-driver "${EMU68_XHCI_SOURCE_DIR}" DEPENDS emu68-pcie-library)
add_stack_project(emu68-genet-driver "${EMU68_GENET_SOURCE_DIR}" DEPENDS emu68-common emu68-gic400-library)

add_custom_target(stack ALL
    DEPENDS
        devicetree.resource
        mailbox.resource
        emu68-common
        emu68-gic400-library
        emu68-pcie-library
        emu68-xhci-driver
        emu68-genet-driver
)