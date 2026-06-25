#include <iostream>

void TestApiSerializer();
void TestApiRouter();
void TestImagePreprocessor();
void TestMeasurementController();
void TestRecordCodec();
void TestRecognition();
void TestStorageRingBuffer();
void TestTimeManager();

int main() {
    TestStorageRingBuffer();
    TestRecognition();
    TestImagePreprocessor();
    TestMeasurementController();
    TestRecordCodec();
    TestApiSerializer();
    TestApiRouter();
    TestTimeManager();
    std::cout << "all host tests passed\n";
    return 0;
}
