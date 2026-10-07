#include <sage-einsums/sage_api.h>
#include <assert.h>
#include <string.h>
int main(void) {
  const char input[]="{\"op\":\"zeros\",\"params\":{\"shape\":[1]}}";
  char* result=sage_api_request(input,sizeof(input)-1);
  assert(result && strstr(result,"\"ok\"")); sage_api_free(result);
  assert(sage_api_request(NULL,1)==NULL); sage_api_free(NULL);
  const char invalid[]={(char)255};
  result=sage_api_request(invalid,1);
  assert(result && strstr(result,"\"error\""));sage_api_free(result);
  return 0;
}
