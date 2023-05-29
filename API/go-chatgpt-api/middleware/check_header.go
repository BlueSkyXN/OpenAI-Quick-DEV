package middleware

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/linweiyuan/go-chatgpt-api/api"
)

func CheckHeaderMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		if c.GetHeader(api.AuthorizationHeader) == "" &&
			c.Request.URL.Path != "/chatgpt/login" &&
			c.Request.URL.Path != "/platform/login" {
			c.AbortWithStatusJSON(http.StatusUnauthorized, api.ReturnMessage("Missing accessToken."))
			return
		}

		c.Header("Content-Type", "application/json")
		c.Next()
	}
}
