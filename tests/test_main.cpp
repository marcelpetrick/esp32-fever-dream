#include <iostream>

void TestApiSerializer();
void TestImagePreprocessor();
void TestRecognition();
void TestStorageRingBuffer();
void TestTimeManager();

int main() {
    TestStorageRingBuffer();
    TestRecognition();
    TestImagePreprocessor();
    TestApiSerializer();
    TestTimeManager();
    std::cout << "all host tests passed\n";
    return 0;
}
