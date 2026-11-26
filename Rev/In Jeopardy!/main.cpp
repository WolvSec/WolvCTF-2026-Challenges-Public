#include <iostream>
#include <string>
using std::string;
using std::cin;
using std::cout;
using std::endl;

string key() {
	string solution;
	solution += char(0x74);
	solution += char(0x68);
	solution += char(0x65);
	solution += char(0x20);
	solution += char(0x66);
	solution += char(0x6C);
	solution += char(0x61);
	solution += char(0x67);
	solution += char(0x3F);
	solution += char(0x21);
	return solution;
}

void print_key_message() {
	string encoded_flag = "\x7a\x66\x77\x69\x7e\x46\x6b\x37\x34\x34\x48\x71\x6a\x36\x38\x30\x69\x33\x55\x62\x77\x5a\x33\x30\x4b\x58\x51\x47\x55\x36\x47\x80";
	string result = "";
	for (unsigned char c : encoded_flag) {
		result += char(c - 3);
	}
	cout << "Correct! " << endl << result << endl;
}

int main() {
	cout << "This password is used to gain the flag from the user in the Jeopardy Rev challenge." << endl;
	string response;
	while (getline(cin, response)) {
		if (response == "What is " + key()) {
			print_key_message();
			cin >> response; // Holds the program open
			break;
		} else if (string::npos == response.find("What is ")) {
			cout << "Incorrect. Try starting your statement with What is" << endl;
		} else {
			cout << "Incorrect." << endl;
		}
	}
	return 0;
}