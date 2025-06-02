# RPC endpoint
RPC = "https://testnet.dplabs-internal.com"

# Налаштування виконання
RETRIES_PER_ACTION = 3                  # Скільки разів повторювати дію, якщо вона не вдалась
DELAY_BETWEEN_RETRIES = (5, 10)          # Затримка між повторами дії при помилці, сек (від, до)
DELAY_BETWEEN_ACTIONS = (60, 300)          # Затримка між діями одного гаманця (наприклад, між свапами)

# Налаштування виконання між гаманцями
DELAY_BETWEEN_WALLETS = (40, 200)         # Затримка між обробкою різних гаманців
RANDOMIZE_WALLETS_ORDER = True         # Обробляти гаманці підряд чи випадково, True - рандомно, False - підряд



ALL_IN_SETTINGS = {
    "swap_phrs_to_usdc": (2, 3),
    "swap_usdc_to_phrs": (1, 3),
    "send_to_self": (10, 15),
    "add_liquidity": (0, 1),
    "deploy_contract": (0, 1),
    "mint_nft": (0, 1),
    "checkin": True
}