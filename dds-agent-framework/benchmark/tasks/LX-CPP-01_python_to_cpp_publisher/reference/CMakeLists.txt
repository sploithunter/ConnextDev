cmake_minimum_required(VERSION 3.10)
project(HelloWorldPublisher CXX)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find RTI Connext DDS
# Set CONNEXTDDS_DIR to $NDDSHOME if not already set
if(NOT DEFINED CONNEXTDDS_DIR)
    if(DEFINED ENV{NDDSHOME})
        set(CONNEXTDDS_DIR $ENV{NDDSHOME})
    else()
        message(FATAL_ERROR "CONNEXTDDS_DIR or NDDSHOME must be set")
    endif()
endif()

list(APPEND CMAKE_MODULE_PATH "${CONNEXTDDS_DIR}/resource/cmake")
find_package(RTIConnextDDS "7.0.0" REQUIRED COMPONENTS core)

# Generate type support from IDL
include(ConnextDdsCodegen)
connextdds_rtiddsgen(
    INPUT_FILE "${CMAKE_CURRENT_SOURCE_DIR}/HelloWorld.idl"
    OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/generated"
    LANG "C++11"
)

# Create executable
add_executable(publisher 
    publisher.cxx
    ${HelloWorld_CXX11_SOURCES}
)

target_include_directories(publisher PRIVATE
    ${CMAKE_CURRENT_BINARY_DIR}/generated
)

target_link_libraries(publisher 
    RTIConnextDDS::cpp2_api
)

# Optional: Install target
install(TARGETS publisher DESTINATION bin)

