import NextAuth from "next-auth";
import type { NextAuthConfig } from "next-auth";
import Google from "next-auth/providers/google";
import MicrosoftEntraID from "next-auth/providers/microsoft-entra-id";

// Dynamic OIDC provider for custom IdPs (Okta, Keycloak, Auth0, etc.)
function getCustomOIDCProvider() {
  const issuer = process.env.OIDC_ISSUER;
  const clientId = process.env.OIDC_CLIENT_ID;
  const clientSecret = process.env.OIDC_CLIENT_SECRET;
  
  if (!issuer || !clientId || !clientSecret) {
    return null;
  }
  
  return {
    id: "custom-oidc",
    name: process.env.OIDC_PROVIDER_NAME || "SSO",
    type: "oidc" as const,
    issuer,
    clientId,
    clientSecret,
    authorization: { params: { scope: "openid email profile" } },
    profile(profile: any) {
      return {
        id: profile.sub,
        name: profile.name || profile.preferred_username,
        email: profile.email,
        image: profile.picture,
      };
    },
  };
}

// Build providers list based on env config
function getProviders() {
  const providers: any[] = [];
  
  // Google
  if (process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET) {
    providers.push(Google({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
    }));
  }
  
  // Microsoft Entra ID (Azure AD)
  if (process.env.AZURE_AD_CLIENT_ID && process.env.AZURE_AD_CLIENT_SECRET && process.env.AZURE_AD_TENANT_ID) {
    providers.push(MicrosoftEntraID({
      clientId: process.env.AZURE_AD_CLIENT_ID,
      clientSecret: process.env.AZURE_AD_CLIENT_SECRET,
      issuer: `https://login.microsoftonline.com/${process.env.AZURE_AD_TENANT_ID}/v2.0`,
    }));
  }
  
  // Custom OIDC (Okta, Keycloak, Auth0, etc.)
  const customOIDC = getCustomOIDCProvider();
  if (customOIDC) {
    providers.push(customOIDC);
  }
  
  return providers;
}

const config: NextAuthConfig = {
  providers: getProviders(),
  // Don't set custom pages - let the SignInGate handle login UI
  // pages: {
  //   signIn: "/",
  //   error: "/",
  // },
  callbacks: {
    async jwt({ token, account, profile }) {
      // On initial sign in, store provider info
      if (account) {
        token.accessToken = account.access_token;
        token.idToken = account.id_token;
        token.provider = account.provider;
      }
      if (profile) {
        token.email = profile.email;
        token.name = profile.name;
      }
      return token;
    },
    async session({ session, token }) {
      // Make tokens available to the client session
      session.accessToken = token.accessToken as string | undefined;
      session.idToken = token.idToken as string | undefined;
      session.provider = token.provider as string | undefined;
      return session;
    },
  },
  session: {
    strategy: "jwt",
    maxAge: 7 * 24 * 60 * 60, // 7 days
  },
  trustHost: true,
};

export const { handlers, signIn, signOut, auth } = NextAuth(config);

// Type augmentation for session
declare module "next-auth" {
  interface Session {
    accessToken?: string;
    idToken?: string;
    provider?: string;
  }
}

