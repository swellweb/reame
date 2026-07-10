# Install script for directory: /Volumes/Progetti Sviluppo/IA/Sovrano/third_party/llama.cpp/ggml

# Set the install prefix
if(NOT DEFINED CMAKE_INSTALL_PREFIX)
  set(CMAKE_INSTALL_PREFIX "/usr/local")
endif()
string(REGEX REPLACE "/$" "" CMAKE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}")

# Set the install configuration name.
if(NOT DEFINED CMAKE_INSTALL_CONFIG_NAME)
  if(BUILD_TYPE)
    string(REGEX REPLACE "^[^A-Za-z0-9_]+" ""
           CMAKE_INSTALL_CONFIG_NAME "${BUILD_TYPE}")
  else()
    set(CMAKE_INSTALL_CONFIG_NAME "Debug")
  endif()
  message(STATUS "Install configuration: \"${CMAKE_INSTALL_CONFIG_NAME}\"")
endif()

# Set the component getting installed.
if(NOT CMAKE_INSTALL_COMPONENT)
  if(COMPONENT)
    message(STATUS "Install component: \"${COMPONENT}\"")
    set(CMAKE_INSTALL_COMPONENT "${COMPONENT}")
  else()
    set(CMAKE_INSTALL_COMPONENT)
  endif()
endif()

# Is this installation the result of a crosscompile?
if(NOT DEFINED CMAKE_CROSSCOMPILING)
  set(CMAKE_CROSSCOMPILING "FALSE")
endif()

# Set path to fallback-tool for dependency-resolution.
if(NOT DEFINED CMAKE_OBJDUMP)
  set(CMAKE_OBJDUMP "/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/objdump")
endif()

if(NOT CMAKE_INSTALL_LOCAL_ONLY)
  # Include the install script for the subdirectory.
  include("/Volumes/Progetti Sviluppo/IA/Sovrano/build-tsan/third_party/llama.cpp/ggml/src/cmake_install.cmake")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib" TYPE SHARED_LIBRARY FILES
    "/Volumes/Progetti Sviluppo/IA/Sovrano/build-tsan/bin/libggml.0.15.3.dylib"
    "/Volumes/Progetti Sviluppo/IA/Sovrano/build-tsan/bin/libggml.0.dylib"
    )
  foreach(file
      "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libggml.0.15.3.dylib"
      "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libggml.0.dylib"
      )
    if(EXISTS "${file}" AND
       NOT IS_SYMLINK "${file}")
      execute_process(COMMAND /usr/bin/install_name_tool
        -delete_rpath "/Volumes/Progetti Sviluppo/IA/Sovrano/build-tsan/bin"
        "${file}")
      if(CMAKE_INSTALL_DO_STRIP)
        execute_process(COMMAND "/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/strip" -x "${file}")
      endif()
    endif()
  endforeach()
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib" TYPE SHARED_LIBRARY FILES "/Volumes/Progetti Sviluppo/IA/Sovrano/build-tsan/bin/libggml.dylib")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/include" TYPE FILE FILES
    "/Volumes/Progetti Sviluppo/IA/Sovrano/third_party/llama.cpp/ggml/include/ggml.h"
    "/Volumes/Progetti Sviluppo/IA/Sovrano/third_party/llama.cpp/ggml/include/ggml-cpu.h"
    "/Volumes/Progetti Sviluppo/IA/Sovrano/third_party/llama.cpp/ggml/include/ggml-alloc.h"
    "/Volumes/Progetti Sviluppo/IA/Sovrano/third_party/llama.cpp/ggml/include/ggml-backend.h"
    "/Volumes/Progetti Sviluppo/IA/Sovrano/third_party/llama.cpp/ggml/include/ggml-blas.h"
    "/Volumes/Progetti Sviluppo/IA/Sovrano/third_party/llama.cpp/ggml/include/ggml-cann.h"
    "/Volumes/Progetti Sviluppo/IA/Sovrano/third_party/llama.cpp/ggml/include/ggml-cpp.h"
    "/Volumes/Progetti Sviluppo/IA/Sovrano/third_party/llama.cpp/ggml/include/ggml-cuda.h"
    "/Volumes/Progetti Sviluppo/IA/Sovrano/third_party/llama.cpp/ggml/include/ggml-opt.h"
    "/Volumes/Progetti Sviluppo/IA/Sovrano/third_party/llama.cpp/ggml/include/ggml-metal.h"
    "/Volumes/Progetti Sviluppo/IA/Sovrano/third_party/llama.cpp/ggml/include/ggml-rpc.h"
    "/Volumes/Progetti Sviluppo/IA/Sovrano/third_party/llama.cpp/ggml/include/ggml-virtgpu.h"
    "/Volumes/Progetti Sviluppo/IA/Sovrano/third_party/llama.cpp/ggml/include/ggml-sycl.h"
    "/Volumes/Progetti Sviluppo/IA/Sovrano/third_party/llama.cpp/ggml/include/ggml-vulkan.h"
    "/Volumes/Progetti Sviluppo/IA/Sovrano/third_party/llama.cpp/ggml/include/ggml-webgpu.h"
    "/Volumes/Progetti Sviluppo/IA/Sovrano/third_party/llama.cpp/ggml/include/ggml-zendnn.h"
    "/Volumes/Progetti Sviluppo/IA/Sovrano/third_party/llama.cpp/ggml/include/ggml-openvino.h"
    "/Volumes/Progetti Sviluppo/IA/Sovrano/third_party/llama.cpp/ggml/include/gguf.h"
    )
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib" TYPE SHARED_LIBRARY FILES
    "/Volumes/Progetti Sviluppo/IA/Sovrano/build-tsan/bin/libggml-base.0.15.3.dylib"
    "/Volumes/Progetti Sviluppo/IA/Sovrano/build-tsan/bin/libggml-base.0.dylib"
    )
  foreach(file
      "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libggml-base.0.15.3.dylib"
      "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libggml-base.0.dylib"
      )
    if(EXISTS "${file}" AND
       NOT IS_SYMLINK "${file}")
      if(CMAKE_INSTALL_DO_STRIP)
        execute_process(COMMAND "/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/strip" -x "${file}")
      endif()
    endif()
  endforeach()
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib" TYPE SHARED_LIBRARY FILES "/Volumes/Progetti Sviluppo/IA/Sovrano/build-tsan/bin/libggml-base.dylib")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/cmake/ggml" TYPE FILE FILES
    "/Volumes/Progetti Sviluppo/IA/Sovrano/build-tsan/third_party/llama.cpp/ggml/ggml-config.cmake"
    "/Volumes/Progetti Sviluppo/IA/Sovrano/build-tsan/third_party/llama.cpp/ggml/ggml-version.cmake"
    )
endif()

string(REPLACE ";" "\n" CMAKE_INSTALL_MANIFEST_CONTENT
       "${CMAKE_INSTALL_MANIFEST_FILES}")
if(CMAKE_INSTALL_LOCAL_ONLY)
  file(WRITE "/Volumes/Progetti Sviluppo/IA/Sovrano/build-tsan/third_party/llama.cpp/ggml/install_local_manifest.txt"
     "${CMAKE_INSTALL_MANIFEST_CONTENT}")
endif()
