cmake_minimum_required(VERSION 3.5)
if(NOT DEFINED CMAKE_TOOLCHAIN_FILE)
  if(DEFINED ENV{VITASDK})
    set(CMAKE_TOOLCHAIN_FILE "$ENV{VITASDK}/share/vita.toolchain.cmake" CACHE PATH "toolchain")
  else()
    message(FATAL_ERROR "Set VITASDK env var")
  endif()
endif()

project(mcserver_mod)
include("${VITASDK}/share/vita.cmake" REQUIRED)
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wall -O2 -nostdlib -fno-builtin")

add_executable(${PROJECT_NAME} src/main.c)
target_link_libraries(${PROJECT_NAME}
  taihen_stub
  SceNet_stub
  SceNetCtl_stub
  SceIofilemgr_stub
  SceLibKernel_stub
  SceKernelThreadMgr_stub
  gcc
)
vita_create_self(${PROJECT_NAME}.suprx ${PROJECT_NAME}
  CONFIG ${CMAKE_SOURCE_DIR}/config.yml UNSAFE)
