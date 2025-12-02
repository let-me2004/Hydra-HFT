cmake_minimum_required(VERSION 3.10)
project(HydraCore)

set(CMAKE_CXX_STANDARD 20)

# 1. Find Packages
find_package(Boost REQUIRED COMPONENTS system thread)
find_package(OpenSSL REQUIRED)
find_package(CURL REQUIRED) 

# 2. Include Headers (Both our code and CURL/Boost)
include_directories(include/core)
include_directories(${CMAKE_SOURCE_DIR}/../shared_defs)
include_directories(${CURL_INCLUDE_DIRS}) # <--- FIX 1

# 3. Create Executable
add_executable(hydra_engine src/main.cpp)

# 4. Link Libraries (Using legacy variable for CURL to be safe)
target_link_libraries(hydra_engine 
    Boost::system 
    Boost::thread 
    OpenSSL::SSL 
    OpenSSL::Crypto
    ${CURL_LIBRARIES}     # <--- FIX 2 (Was CURL::libcurl)
    rt 
)