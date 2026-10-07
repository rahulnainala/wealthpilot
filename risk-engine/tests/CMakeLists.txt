find_package(GTest CONFIG REQUIRED)

add_executable(risk_engine_tests monte_carlo_test.cpp)
target_link_libraries(risk_engine_tests PRIVATE risk_engine_lib GTest::gtest GTest::gtest_main)

include(GoogleTest)
gtest_discover_tests(risk_engine_tests DISCOVERY_MODE PRE_TEST)
